from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core import NotFoundError, get_session
from src.core.config import get_settings
from src.models import Case

from .schemas import (
    AIQueryRequest,
    AIQueryResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatSession,
)
from .service import investigation_assistant

router = APIRouter(prefix="/ai", tags=["ai"])
_settings = get_settings()


class ChatSessionStore:
    """Redis-backed chat session storage.

    Chat history used to live in a class-level in-memory dict, which meant it
    was lost on every process restart and wasn't shared across multiple
    uvicorn/gunicorn workers (each worker had its own dict). Storing sessions
    in Redis (the same REDIS_URL already used for Celery) fixes both.
    """

    _redis: Optional["aioredis.Redis"] = None
    _KEY_PREFIX = "ai:chat_session:"
    _TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days

    @classmethod
    def _get_redis(cls) -> "aioredis.Redis":
        if cls._redis is None:
            cls._redis = aioredis.from_url(_settings.REDIS_URL, decode_responses=True)
        return cls._redis

    @classmethod
    def _key(cls, session_id: str) -> str:
        return f"{cls._KEY_PREFIX}{session_id}"

    @classmethod
    async def get(cls, session_id: str) -> ChatSession | None:
        raw = await cls._get_redis().get(cls._key(session_id))
        if not raw:
            return None
        return ChatSession.model_validate_json(raw)

    @classmethod
    async def _save(cls, session: ChatSession) -> None:
        await cls._get_redis().set(
            cls._key(session.session_id), session.model_dump_json(), ex=cls._TTL_SECONDS
        )

    @classmethod
    async def get_or_create(cls, session_id: str | None = None) -> ChatSession:
        if session_id:
            existing = await cls.get(session_id)
            if existing:
                return existing
        new_session = ChatSession(session_id=session_id or str(uuid4()))
        await cls._save(new_session)
        return new_session

    @classmethod
    async def update(cls, session: ChatSession) -> None:
        session.updated_at = datetime.utcnow()
        await cls._save(session)

    @classmethod
    async def add_message(cls, session_id: str, message: ChatMessage) -> ChatSession:
        session = await cls.get(session_id)
        if not session:
            session = ChatSession(session_id=session_id)
        session.messages.append(message)
        session.updated_at = datetime.utcnow()
        await cls._save(session)
        return session

    @classmethod
    async def delete(cls, session_id: str) -> bool:
        deleted = await cls._get_redis().delete(cls._key(session_id))
        return bool(deleted)


@router.post(
    "/query",
    response_model=AIQueryResponse,
    summary="Query investigation assistant",
    description="Query the investigation assistant with a question about a case or wallet.",
)
async def query_investigation_assistant(
    request: AIQueryRequest,
    session: AsyncSession = Depends(get_session),
):
    if request.case_id:
        case = await session.get(Case, request.case_id)
        if not case:
            raise NotFoundError("Case", request.case_id)

    response = await investigation_assistant.answer_query(
        query=request.query,
        case_id=request.case_id,
        wallet_id=request.wallet_id,
    )

    # src.ai.service defines its own QueryType/ConfidenceLevel/Evidence rather
    # than reusing these schemas classes; pydantic validates str-enum fields
    # by value (safe, since both enums share the same members) and Evidence
    # via schemas.Evidence's from_attributes=True, so this is a real but
    # harmless cross-module type mismatch.
    return AIQueryResponse(
        answer=response.answer,
        query_type=response.query_type,  # type: ignore[arg-type]
        confidence=response.confidence,  # type: ignore[arg-type]
        evidence=response.evidence,  # type: ignore[arg-type]
        follow_up_questions=response.follow_up_questions,
        metadata=response.metadata,
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with assistant",
    description="Chat with the investigation assistant and maintain conversation history.",
)
async def chat_with_assistant(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
):
    chat_session = await ChatSessionStore.get_or_create(request.session_id)

    if request.case_id:
        chat_session.case_id = request.case_id

    user_message = ChatMessage(role="user", content=request.message)
    chat_session = await ChatSessionStore.add_message(chat_session.session_id, user_message)

    case_id = request.case_id or chat_session.case_id

    ai_response = await investigation_assistant.answer_query(
        query=request.message,
        case_id=case_id,
        wallet_id=request.wallet_id,
    )

    message_metadata = {
        "query_type": ai_response.query_type.value,
        "confidence": ai_response.confidence.value,
        "evidence_count": len(ai_response.evidence),
        **(ai_response.metadata or {}),
        "evidence": [
            e.model_dump() if hasattr(e, "model_dump") else (e.dict() if hasattr(e, "dict") else dict(e))
            for e in ai_response.evidence
        ] if ai_response.evidence else [],
    }

    assistant_message = ChatMessage(
        role="assistant",
        content=ai_response.answer,
        metadata=message_metadata,
    )
    chat_session = await ChatSessionStore.add_message(chat_session.session_id, assistant_message)

    suggested_actions = ai_response.follow_up_questions[:3]

    return ChatResponse(
        session_id=chat_session.session_id,
        message=assistant_message,
        suggested_actions=suggested_actions,
    )


@router.get(
    "/chat/history/{session_id}",
    summary="Get chat history",
    description="Retrieve chat history for a session.",
)
async def get_chat_history(
    session_id: str,
):
    session = await ChatSessionStore.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return {
        "session_id": session.session_id,
        "case_id": session.case_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
                "metadata": m.metadata,
            }
            for m in session.messages
        ],
    }


@router.delete(
    "/chat/history/{session_id}",
    summary="Delete chat history",
    description="Delete a chat session and its history.",
)
async def delete_chat_history(
    session_id: str,
):
    await ChatSessionStore.delete(session_id)
    return {"status": "deleted"}


@router.get(
    "/capabilities",
    summary="Get AI capabilities",
    description="Retrieve AI assistant capabilities, provider info, and supported query types.",
)
async def get_ai_capabilities():
    mode = investigation_assistant.mode
    provider = investigation_assistant.provider

    # Reported from the provider actually in use, not from settings. This used
    # to answer with ANTHROPIC_MODEL whatever the deployment was configured
    # with, so an OpenRouter deployment was described as talking to the
    # Anthropic API, under a model name it had never heard of.
    template_description = (
        "Responses are generated from deterministic templates over real "
        "investigation evidence (no live LLM call) - either no API key is "
        "configured, or AI_MODE=demo was set explicitly."
    )
    descriptions = {
        "live": f"Responses are generated by {provider.provider_name} ({provider.model_name}).",
        "demo": template_description,
        "disabled": "AI assistance is disabled on this deployment (AI_MODE=disabled). "
        "The rest of TRACE-X continues to function normally.",
    }
    description = descriptions[mode]

    # A live provider whose calls are failing still answers, from the same
    # templates the demo provider uses. Saying so is the difference between a
    # deployment an operator can trust and one that quietly stopped calling
    # its model -- which is exactly what an expired or renamed model id does.
    degraded = mode == "live" and provider.degraded
    if degraded:
        description = (
            f"{provider.provider_name} calls are failing, so responses are "
            f"falling back to deterministic templates over real investigation "
            f"evidence. Last error: {provider.last_error}"
        )

    return {
        "mode": mode,
        "provider": provider.provider_name,
        "model": provider.model_name if mode == "live" else None,
        "degraded": degraded,
        "degraded_reason": provider.last_error if degraded else None,
        "description": description,
        "capabilities": [
            {
                "name": "Risk Analysis",
                "description": "Explainable risk scoring with factor breakdown for wallets and cases",
                "example_queries": [
                    "What's the risk score for wallet 0xa241ec91A7D0c2c8bf11d01C168579Ee1201a209?",
                    "Show me the risk distribution for case TRX-20240115-0042",
                    "Why is wallet 0x... flagged as high risk?",
                ],
            },
            {
                "name": "VASP Attribution",
                "description": "Trace funds to nearest exchange/VASP with confidence levels",
                "example_queries": [
                    "Where did funds from wallet 0x... go?",
                    "Which exchange did the money end up at?",
                    "Show me the attribution path for wallet 0x...",
                ],
            },
            {
                "name": "Pattern Detection",
                "description": "Detect peel chains, round amounts, rapid movement, mixer interactions",
                "example_queries": [
                    "Any suspicious patterns on Ethereum?",
                    "Detect peel chains in case TRX-...",
                    "Show me mixer interactions for wallet 0x...",
                ],
            },
            {
                "name": "Fund Flow Tracing",
                "description": "Multi-hop fund flow analysis with path finding to VASPs",
                "example_queries": [
                    "Trace the money from wallet 0x...",
                    "Show me the fund flow for case TRX-...",
                    "What's the path from 0x... to the nearest exchange?",
                ],
            },
            {
                "name": "Entity Intelligence",
                "description": "Look up known entities (exchanges, mixers, bridges, sanctioned addresses)",
                "example_queries": [
                    "Who owns address 0x...?",
                    "Is 0x... a known mixer?",
                    "What entity is 0x... associated with?",
                ],
            },
            {
                "name": "Case Overview",
                "description": "Summarize case status, wallets, investigations, risk distribution",
                "example_queries": [
                    "Tell me about case TRX-20240115-0042",
                    "What's the status of my investigations?",
                    "Case summary for TRX-...",
                ],
            },
            {
                "name": "Timeline Analysis",
                "description": "Transaction timeline and temporal flow analysis",
                "example_queries": [
                    "Show me transaction timeline for wallet 0x...",
                    "When was the peak activity for this wallet?",
                ],
            },
        ],
        "confidence_levels": [
            {"level": "CONFIRMED", "description": "Verified on-chain + off-chain correlation"},
            {
                "level": "HIGH_CONFIDENCE",
                "description": "Strong heuristic + multiple corroborating signals",
            },
            {"level": "PROBABLE", "description": "Single strong signal or multiple weak signals"},
            {"level": "UNKNOWN", "description": "Insufficient evidence"},
        ],
    }


@router.post(
    "/generate-narrative",
    summary="Generate investigation narrative",
    description="Generate a comprehensive investigation narrative for a case with wallet analysis and recommendations.",
)
async def generate_investigation_narrative(
    case_id: UUID,
    wallet_ids: list[UUID] | None = None,
    session: AsyncSession = Depends(get_session),
):
    case = await session.get(Case, case_id)
    if not case:
        raise NotFoundError("Case", str(case_id))

    from sqlalchemy import select

    from src.models import InvestigationRun, Wallet

    wallet_query = select(Wallet).where(Wallet.case_id == case_id)
    if wallet_ids:
        wallet_query = wallet_query.where(Wallet.id.in_(wallet_ids))
    result = await session.execute(wallet_query)
    wallets = list(result.scalars().all())

    inv_result = await session.execute(
        select(InvestigationRun).where(InvestigationRun.case_id == case_id)
    )
    investigations = list(inv_result.scalars().all())

    chains = list({w.chain for w in wallets})

    narrative_parts = [
        f"# Investigation Narrative: {case.title}",
        f"**Case Number:** {case.case_number}",
        f"**Classification:** {case.crime_type.replace('_', ' ').title()}",
        f"**Status:** {case.status.replace('_', ' ').title()}",
        f"**Investigation Period:** {len(investigations)} runs ({len([i for i in investigations if i.status == 'completed'])} completed)",
        "",
        "## Executive Summary",
        f"This investigation analyzed **{len(wallets)} wallet addresses** across **{len({w.chain for w in wallets})} blockchain(s)**. "
        f"**{len([w for w in wallets if float(w.risk_score or 0) >= 75])} wallets** were classified as high risk (score ≥ 75). "
        f"**{len([w for w in wallets if w.entity_name and w.entity_confidence in ['CONFIRMED', 'HIGH_CONFIDENCE']])} wallets** "
        f"were attributed to known entities with high confidence.",
        "",
        "## Wallet Analysis",
    ]

    for w in wallets[:10]:
        risk_level = (
            "CRITICAL"
            if float(w.risk_score or 0) >= 75
            else "HIGH"
            if float(w.risk_score or 0) >= 50
            else "MEDIUM"
            if float(w.risk_score or 0) >= 25
            else "LOW"
        )
        entity_info = f" → **{w.entity_name}** ({w.entity_confidence})" if w.entity_name else ""
        narrative_parts.append(
            f"- **{w.address[:10]}...{w.address[-8:]}** ({w.chain}) — {w.label or 'Unlabeled'} — "
            f"Risk: **{risk_level}** ({w.risk_score}/100){entity_info}"
        )

    if len(wallets) > 10:
        narrative_parts.append(f"- ... and {len(wallets) - 10} more wallets")

    narrative_parts.extend(
        [
            "",
            "## Key Findings",
        ]
    )

    high_risk_wallets = [w for w in wallets if float(w.risk_score or 0) >= 75]
    if high_risk_wallets:
        narrative_parts.append(
            f"- **{len(high_risk_wallets)} high-risk wallets** identified requiring priority attention"
        )

    attributed = [
        w
        for w in wallets
        if w.entity_name and w.entity_confidence in ["CONFIRMED", "HIGH_CONFIDENCE"]
    ]
    if attributed:
        exchanges = [w for w in attributed if w.entity_type == "exchange"]
        mixers = [w for w in attributed if w.entity_type == "mixer"]
        narrative_parts.append(
            f"- **{len(exchanges)} exchange attributions** (confirmed/high confidence)"
        )
        if mixers:
            narrative_parts.append(
                f"- **{len(mixers)} mixer interactions** detected — high risk indicator"
            )

    narrative_parts.append(
        f"- **Cross-chain activity** detected across {len(chains)} chains: {', '.join(chains)}"
    )

    completed_inv = [i for i in investigations if i.status == "completed"]
    if completed_inv:
        total_txs = sum(
            i.result_summary.get("transactions_found", 0) for i in completed_inv if i.result_summary
        )
        narrative_parts.append(
            f"- **{len(completed_inv)} completed investigations** analyzed {total_txs} transactions total"
        )

    narrative_parts.extend(
        [
            "",
            "## Recommendations",
            "1. **Priority**: Focus on high-risk wallets with confirmed exchange attributions for subpoena/legal action",
            "2. **Expand tracing**: Increase trace depth for wallets that did not reach VASP endpoints",
            "3. **Monitor**: Set up continuous monitoring for mixer interactions and new wallet creation",
            "4. **Coordinate**: Share confirmed VASP attributions with relevant law enforcement / compliance teams",
            "",
            "---",
            f"*Generated by TRACE-X AI Assistant on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*",
            "*This narrative is based on automated analysis. Human review recommended for legal proceedings.*",
        ]
    )

    fallback_narrative = "\n".join(narrative_parts)

    # Graceful degradation: generate_narrative() calls Claude when
    # ANTHROPIC_API_KEY is configured and otherwise (or on any API failure)
    # returns fallback_narrative unchanged - never a 500.
    case_summary = {
        "title": case.title,
        "case_number": case.case_number,
        "crime_type": case.crime_type,
        "status": case.status,
        "investigation_runs": len(investigations),
        "completed_runs": len([i for i in investigations if i.status == "completed"]),
    }
    wallets_summary = [
        {
            "address": w.address,
            "chain": w.chain,
            "label": w.label,
            "risk_score": float(w.risk_score or 0),
            "entity_name": w.entity_name,
            "entity_type": w.entity_type,
            "entity_confidence": w.entity_confidence,
        }
        for w in wallets[:25]
    ]
    completed_inv = [i for i in investigations if i.status == "completed"]
    findings = {
        "wallet_count": len(wallets),
        "high_risk_wallet_count": len([w for w in wallets if float(w.risk_score or 0) >= 75]),
        "attributed_wallet_count": len(
            [
                w
                for w in wallets
                if w.entity_name and w.entity_confidence in ["CONFIRMED", "HIGH_CONFIDENCE"]
            ]
        ),
        "chains": chains,
        "completed_investigations": len(completed_inv),
        "total_transactions_analyzed": sum(
            i.result_summary.get("transactions_found", 0) for i in completed_inv if i.result_summary
        ),
    }

    narrative = await investigation_assistant.generate_narrative(
        case_summary=case_summary,
        wallets_summary=wallets_summary,
        findings=findings,
        fallback_narrative=fallback_narrative,
    )

    return {
        "case_id": str(case_id),
        "narrative": narrative,
        "generated_at": datetime.utcnow().isoformat(),
    }
