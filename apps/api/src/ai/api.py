from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from src.core import get_session, NotFoundError
from src.models import Case
from src.ai.schemas import AIQueryRequest, AIQueryResponse, ChatRequest, ChatResponse, ChatSession, ChatMessage
from src.ai.service import investigation_assistant

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatSessionStore:
    _sessions: Dict[str, ChatSession] = {}

    @classmethod
    def get_or_create(cls, session_id: Optional[str] = None) -> ChatSession:
        if session_id and session_id in cls._sessions:
            return cls._sessions[session_id]
        new_session = ChatSession(session_id=session_id or str(uuid4()))
        cls._sessions[new_session.session_id] = new_session
        return new_session

    @classmethod
    def update(cls, session: ChatSession) -> None:
        session.updated_at = session.updated_at.__class__.utcnow()
        cls._sessions[session.session_id] = session

    @classmethod
    def add_message(cls, session_id: str, message: ChatMessage) -> ChatSession:
        session = cls._sessions.get(session_id)
        if not session:
            session = ChatSession(session_id=session_id)
            cls._sessions[session_id] = session
        session.messages.append(message)
        session.updated_at = session.updated_at.__class__.utcnow()
        return session


@router.post("/query", response_model=AIQueryResponse)
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

    return AIQueryResponse(
        answer=response.answer,
        query_type=response.query_type,
        confidence=response.confidence,
        evidence=response.evidence,
        follow_up_questions=response.follow_up_questions,
        metadata=response.metadata,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
):
    chat_session = ChatSessionStore.get_or_create(request.session_id)

    if request.case_id:
        chat_session.case_id = request.case_id

    user_message = ChatMessage(role="user", content=request.message)
    chat_session = ChatSessionStore.add_message(chat_session.session_id, user_message)

    case_id = request.case_id or chat_session.case_id

    ai_response = await investigation_assistant.answer_query(
        query=request.message,
        case_id=case_id,
        wallet_id=request.wallet_id,
    )

    assistant_message = ChatMessage(
        role="assistant",
        content=ai_response.answer,
        metadata={
            "query_type": ai_response.query_type.value,
            "confidence": ai_response.confidence.value,
            "evidence_count": len(ai_response.evidence),
        },
    )
    chat_session = ChatSessionStore.add_message(chat_session.session_id, assistant_message)

    suggested_actions = ai_response.follow_up_questions[:3]

    return ChatResponse(
        session_id=chat_session.session_id,
        message=assistant_message,
        suggested_actions=suggested_actions,
    )


@router.get("/chat/history/{session_id}")
async def get_chat_history(
    session_id: str,
):
    session = ChatSessionStore._sessions.get(session_id)
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


@router.delete("/chat/history/{session_id}")
async def delete_chat_history(
    session_id: str,
):
    if session_id in ChatSessionStore._sessions:
        del ChatSessionStore._sessions[session_id]
    return {"status": "deleted"}


@router.get("/capabilities")
async def get_ai_capabilities():
    return {
        "capabilities": [
            {
                "name": "Risk Analysis",
                "description": "Explainable risk scoring with factor breakdown for wallets and cases",
                "example_queries": [
                    "What's the risk score for wallet 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb?",
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
            {"level": "HIGH_CONFIDENCE", "description": "Strong heuristic + multiple corroborating signals"},
            {"level": "PROBABLE", "description": "Single strong signal or multiple weak signals"},
            {"level": "UNKNOWN", "description": "Insufficient evidence"},
        ],
    }


@router.post("/generate-narrative")
async def generate_investigation_narrative(
    case_id: UUID,
    wallet_ids: Optional[List[UUID]] = None,
    session: AsyncSession = Depends(get_session),
):
    case = await session.get(Case, case_id)
    if not case:
        raise NotFoundError("Case", str(case_id))

    from sqlalchemy import select
    from src.models import Wallet, InvestigationRun

    wallet_query = select(Wallet).where(Wallet.case_id == case_id)
    if wallet_ids:
        wallet_query = wallet_query.where(Wallet.id.in_(wallet_ids))
    result = await session.execute(wallet_query)
    wallets = list(result.scalars().all())

    inv_result = await session.execute(select(InvestigationRun).where(InvestigationRun.case_id == case_id))
    investigations = list(inv_result.scalars().all())

    narrative_parts = [
        f"# Investigation Narrative: {case.title}",
        f"**Case Number:** {case.case_number}",
        f"**Classification:** {case.crime_type.replace('_', ' ').title()}",
        f"**Status:** {case.status.replace('_', ' ').title()}",
        f"**Investigation Period:** {len(investigations)} runs ({len([i for i in investigations if i.status == 'completed'])} completed)",
        "",
        "## Executive Summary",
        f"This investigation analyzed **{len(wallets)} wallet addresses** across **{len(set(w.chain for w in wallets))} blockchain(s)**. "
        f"**{len([w for w in wallets if float(w.risk_score or 0) >= 75])} wallets** were classified as high risk (score ≥ 75). "
        f"**{len([w for w in wallets if w.entity_name and w.entity_confidence in ['CONFIRMED', 'HIGH_CONFIDENCE']])} wallets** "
        f"were attributed to known entities with high confidence.",
        "",
        "## Wallet Analysis",
    ]

    for w in wallets[:10]:
        risk_level = "CRITICAL" if float(w.risk_score or 0) >= 75 else "HIGH" if float(w.risk_score or 0) >= 50 else "MEDIUM" if float(w.risk_score or 0) >= 25 else "LOW"
        entity_info = f" → **{w.entity_name}** ({w.entity_confidence})" if w.entity_name else ""
        narrative_parts.append(
            f"- **{w.address[:10]}...{w.address[-8:]}** ({w.chain}) — {w.label or 'Unlabeled'} — "
            f"Risk: **{risk_level}** ({w.risk_score}/100){entity_info}"
        )

    if len(wallets) > 10:
        narrative_parts.append(f"- ... and {len(wallets) - 10} more wallets")

    narrative_parts.extend([
        "",
        "## Key Findings",
    ])

    high_risk_wallets = [w for w in wallets if float(w.risk_score or 0) >= 75]
    if high_risk_wallets:
        narrative_parts.append(f"- **{len(high_risk_wallets)} high-risk wallets** identified requiring priority attention")

    attributed = [w for w in wallets if w.entity_name and w.entity_confidence in ["CONFIRMED", "HIGH_CONFIDENCE"]]
    if attributed:
        exchanges = [w for w in attributed if w.entity_type == "exchange"]
        mixers = [w for w in attributed if w.entity_type == "mixer"]
        narrative_parts.append(f"- **{len(exchanges)} exchange attributions** (confirmed/high confidence)")
        if mixers:
            narrative_parts.append(f"- **{len(mixers)} mixer interactions** detected — high risk indicator")

    narrative_parts.append(f"- **Cross-chain activity** detected across {len(chains)} chains: {', '.join(chains)}")

    completed_inv = [i for i in investigations if i.status == "completed"]
    if completed_inv:
        total_txs = sum(i.result_summary.get("transactions_found", 0) for i in completed_inv if i.result_summary)
        narrative_parts.append(f"- **{len(completed_inv)} completed investigations** analyzed {total_txs} transactions total")

    narrative_parts.extend([
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
    ])

    return {
        "case_id": str(case_id),
        "narrative": "\n".join(narrative_parts),
        "generated_at": datetime.utcnow().isoformat(),
    }


from datetime import datetime