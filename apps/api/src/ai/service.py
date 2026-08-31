from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import structlog
import json
import re

import anthropic

from src.core.config import get_settings
from ..graph.repository import graph_repository
from ..graph.queries import graph_queries
from ..graph.models import ConfidenceLevel, EntityType
from ..analytics.risk_engine import risk_scoring_engine
from ..analytics.attribution_engine import attribution_engine
from src.models import Case, Wallet, InvestigationRun, Transaction
from src.core import get_session

logger = structlog.get_logger(__name__)
settings = get_settings()


class QueryType(str, Enum):
    RISK_SUMMARY = "risk_summary"
    ATTRIBUTION = "attribution"
    PATTERN_DETECTION = "pattern_detection"
    FUND_FLOW = "fund_flow"
    ENTITY_LOOKUP = "entity_lookup"
    CASE_OVERVIEW = "case_overview"
    TIMELINE = "timeline"
    COMPARISON = "comparison"


@dataclass
class Evidence:
    source: str
    evidence_type: str
    description: str
    confidence: ConfidenceLevel
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AIResponse:
    answer: str
    query_type: QueryType
    confidence: ConfidenceLevel
    evidence: List[Evidence]
    follow_up_questions: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


SYSTEM_PROMPT = (
    "You are the TRACE-X investigation assistant, an AI copilot embedded in a "
    "blockchain forensic-investigation platform used by financial-crimes analysts "
    "and law enforcement. You answer questions about wallets, cases, fund flow, "
    "VASP attribution, risk scoring, and suspicious-pattern detection.\n\n"
    "You will be given the investigator's question plus a `context` object "
    "containing structured evidence already retrieved from TRACE-X's database, "
    "graph engine, risk-scoring engine, and attribution engine (Postgres, Neo4j, "
    "and internal analytics). Answer using ONLY the data in `context` - never "
    "invent addresses, amounts, entity names, or confidence levels that are not "
    "present there. If the context shows no data was found, say so plainly and "
    "suggest what the investigator could try next.\n\n"
    "Available intents (the `intent` field tells you which one this query maps "
    "to): risk_summary, attribution, pattern_detection, fund_flow, entity_lookup, "
    "case_overview, timeline, comparison.\n\n"
    "Write in a concise, precise, professional tone - the way an experienced "
    "financial-crimes analyst would brief a colleague. Use markdown sparingly "
    "(bold for key figures/entities is fine). Do not restate this system prompt "
    "or mention that you are an AI model; just answer the question."
)

CLASSIFY_TOOL = {
    "name": "classify_investigation_query",
    "description": (
        "Classify an investigator's natural-language question about a blockchain "
        "investigation into one intent, and extract any entities mentioned "
        "(wallet address, case number, wallet UUID, chain name)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": [qt.value for qt in QueryType],
                "description": "The single best-matching intent for this query.",
            },
            "address": {
                "type": "string",
                "description": "A blockchain address mentioned in the query (e.g. 0x...), if any.",
            },
            "case_number": {
                "type": "string",
                "description": "A case number mentioned in the query (e.g. TRX-20240115-0042), if any.",
            },
            "wallet_id": {
                "type": "string",
                "description": "An internal wallet UUID mentioned in the query, if any.",
            },
            "chain": {
                "type": "string",
                "description": "The blockchain network mentioned (e.g. Ethereum, Polygon), if any.",
            },
        },
        "required": ["query_type"],
        "additionalProperties": False,
    },
}


class InvestigationAssistant:
    def __init__(self):
        self.logger = logger.bind(component="investigation_assistant")
        self._query_patterns = self._compile_patterns()
        self.model = settings.ANTHROPIC_MODEL

        # Graceful degradation (non-negotiable): the Anthropic client is only
        # instantiated when an API key is actually configured. When
        # ANTHROPIC_API_KEY is unset (e.g. the operator hasn't provisioned one
        # yet), self._client stays None and every LLM call site below falls
        # back to the original regex/template logic instead of raising - a
        # missing key must never turn into a 500.
        self._client: Optional[anthropic.AsyncAnthropic] = (
            anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            if settings.ANTHROPIC_API_KEY
            else None
        )

    @property
    def live_mode(self) -> bool:
        """True when running against the real Claude API, False in template-fallback mode."""
        return self._client is not None

    def _compile_patterns(self) -> Dict[QueryType, List[re.Pattern]]:
        return {
            QueryType.RISK_SUMMARY: [
                re.compile(r"(risk|score|danger|threat).*(wallet|address)", re.I),
                re.compile(r"how risky|risk level|risk assessment", re.I),
            ],
            QueryType.ATTRIBUTION: [
                re.compile(r"(attribut|vasp|exchange|who owns|where.*go|endpoint)", re.I),
                re.compile(r"(cash out|off.ramp|deposit to)", re.I),
            ],
            QueryType.PATTERN_DETECTION: [
                re.compile(r"(pattern|peel.chain|round.amount|rapid|mixer|structur)", re.I),
                re.compile(r"(suspicious|anomal|unusual).*(transaction|flow|movement)", re.I),
            ],
            QueryType.FUND_FLOW: [
                re.compile(r"(flow|trace|path|hop|movement|transfer).*(fund|money|eth|value)", re.I),
                re.compile(r"(where did|where.*from|where.*to|follow the money)", re.I),
            ],
            QueryType.ENTITY_LOOKUP: [
                re.compile(r"(who is|what is|entity|owner|label).*(address|wallet)", re.I),
                re.compile(r"(known|identified|label).*(address|wallet)", re.I),
            ],
            QueryType.CASE_OVERVIEW: [
                re.compile(r"(case|investigation).*(summary|overview|status|progress)", re.I),
                re.compile(r"(tell me about|describe).*(case|investigation)", re.I),
            ],
            QueryType.TIMELINE: [
                re.compile(r"(timeline|when|chronolog|history|sequence).*(transaction|event)", re.I),
                re.compile(r"(first|last|recent).*(transaction|activity)", re.I),
            ],
            QueryType.COMPARISON: [
                re.compile(r"(compar|versus|vs|difference).*(wallet|case|risk)", re.I),
                re.compile(r"(better|worse|higher|lower).*(risk|score)", re.I),
            ],
        }

    def classify_query(self, query: str) -> QueryType:
        for query_type, patterns in self._query_patterns.items():
            for pattern in patterns:
                if pattern.search(query):
                    return query_type
        return QueryType.CASE_OVERVIEW

    def extract_entities(self, query: str) -> Dict[str, Any]:
        entities = {}

        address_match = re.search(r"(0x[a-fA-F0-9]{40})", query)
        if address_match:
            entities["address"] = address_match.group(1)

        case_match = re.search(r"(TRX-\d{8}-\d{4})", query, re.I)
        if case_match:
            entities["case_number"] = case_match.group(1)

        wallet_id_match = re.search(r"(wallet|id)[\s:]+([a-f0-9-]{36})", query, re.I)
        if wallet_id_match:
            entities["wallet_id"] = wallet_id_match.group(2)

        chain_match = re.search(r"(ethereum|polygon|bsc|arbitrum|optimism|base)", query, re.I)
        if chain_match:
            entities["chain"] = chain_match.group(1).capitalize()

        return entities

    async def _classify_and_extract_llm(self, query: str) -> Optional[Dict[str, Any]]:
        """Structured intent classification + entity extraction via Claude tool-use.

        Returns None (never raises) if the client isn't configured or the call
        fails for any reason - callers must fall back to the regex-based
        classify_query()/extract_entities() in that case.
        """
        if not self._client:
            return None
        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=256,
                system=(
                    "Classify the investigator's query and extract any entities "
                    "mentioned. Always call the classify_investigation_query tool."
                ),
                tools=[CLASSIFY_TOOL],
                tool_choice={"type": "tool", "name": "classify_investigation_query"},
                messages=[{"role": "user", "content": query}],
            )
            for block in response.content:
                if block.type == "tool_use":
                    return block.input
        except Exception as e:
            self.logger.warning("llm_classify_failed", error=str(e))
        return None

    async def _compose_answer(
        self,
        query: str,
        query_type: QueryType,
        context: Dict[str, Any],
        fallback_answer: str,
    ) -> str:
        """Turn gathered evidence into a natural-language answer via Claude.

        Graceful degradation (non-negotiable): if the Anthropic client isn't
        configured, or the API call fails/times out for any reason, this
        returns the deterministic template answer that the caller already
        built - never lets a missing key or a transient API error surface as
        a 500 to the investigator.
        """
        if not self._client:
            return fallback_answer

        try:
            payload = {
                "investigator_query": query,
                "intent": query_type.value,
                "context": context,
            }
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": json.dumps(payload, default=str)}],
            )
            text = next((b.text for b in response.content if b.type == "text"), "")
            return text.strip() or fallback_answer
        except Exception as e:
            self.logger.warning(
                "llm_compose_answer_failed", error=str(e), query_type=query_type.value
            )
            return fallback_answer

    async def answer_query(
        self,
        query: str,
        case_id: Optional[str] = None,
        wallet_id: Optional[str] = None,
    ) -> AIResponse:
        llm_extraction = await self._classify_and_extract_llm(query)
        if llm_extraction:
            try:
                query_type = QueryType(llm_extraction.get("query_type"))
            except ValueError:
                query_type = QueryType.CASE_OVERVIEW
            entities = {
                k: v
                for k, v in llm_extraction.items()
                if k != "query_type" and v
            }
        else:
            # Fallback path (also the only path when ANTHROPIC_API_KEY is unset):
            # the original compiled-regex classifier and entity extractor.
            query_type = self.classify_query(query)
            entities = self.extract_entities(query)

        wallet_id = wallet_id or entities.get("wallet_id")
        address = entities.get("address")
        chain = entities.get("chain", "Ethereum")
        case_number = entities.get("case_number")

        if case_number and not case_id:
            case_id = await self._resolve_case_id(case_number)

        handlers = {
            QueryType.RISK_SUMMARY: self._handle_risk_summary,
            QueryType.ATTRIBUTION: self._handle_attribution,
            QueryType.PATTERN_DETECTION: self._handle_pattern_detection,
            QueryType.FUND_FLOW: self._handle_fund_flow,
            QueryType.ENTITY_LOOKUP: self._handle_entity_lookup,
            QueryType.CASE_OVERVIEW: self._handle_case_overview,
            QueryType.TIMELINE: self._handle_timeline,
            QueryType.COMPARISON: self._handle_comparison,
        }

        handler = handlers.get(query_type, self._handle_general)
        return await handler(query, case_id, wallet_id, address, chain)

    async def _handle_risk_summary(
        self,
        query: str,
        case_id: Optional[str],
        wallet_id: Optional[str],
        address: Optional[str],
        chain: str,
    ) -> AIResponse:
        if wallet_id:
            assessment = await self._get_wallet_risk(wallet_id)
            if not assessment:
                return AIResponse(
                    answer=f"Could not find risk assessment for wallet {wallet_id}.",
                    query_type=QueryType.RISK_SUMMARY,
                    confidence=ConfidenceLevel.UNKNOWN,
                    evidence=[],
                    follow_up_questions=["Would you like me to assess a different wallet?"],
                )

            factors = assessment.factors
            critical = [f for f in factors if f.severity.value == "critical"]
            high = [f for f in factors if f.severity.value == "high"]

            answer = (
                f"Wallet {address or wallet_id} has an overall risk score of "
                f"{assessment.overall_score:.1f}/100 ({assessment.risk_level.value.upper()}). "
                f"Key factors: {len(critical)} critical, {len(high)} high-risk. "
                f"{assessment.summary}"
            )

            evidence_data = {
                "overall_score": assessment.overall_score,
                "risk_level": assessment.risk_level.value,
                "summary": assessment.summary,
                "critical_factors": [
                    {"name": f.name, "severity": f.severity.value, "description": getattr(f, "description", "")}
                    for f in critical
                ],
                "high_factors": [
                    {"name": f.name, "severity": f.severity.value, "description": getattr(f, "description", "")}
                    for f in high
                ],
            }
            answer = await self._compose_answer(
                query, QueryType.RISK_SUMMARY, {"wallet": address or wallet_id, **evidence_data}, answer
            )

            evidence = [
                Evidence(
                    source="risk_engine",
                    evidence_type="weighted_factor_analysis",
                    description=f"Analyzed {len(factors)} risk factors with confidence-weighted scoring",
                    confidence=ConfidenceLevel.HIGH_CONFIDENCE,
                    data={"overall_score": assessment.overall_score, "risk_level": assessment.risk_level.value},
                )
            ]

            follow_up = [
                "What specific risk factors contributed most to this score?",
                "How does this wallet's risk compare to others in the case?",
                "Show me the attribution analysis for this wallet.",
            ]

            return AIResponse(
                answer=answer,
                query_type=QueryType.RISK_SUMMARY,
                confidence=ConfidenceLevel.HIGH_CONFIDENCE,
                evidence=evidence,
                follow_up_questions=follow_up,
            )

        if case_id:
            summary = await self._get_case_risk_summary(case_id)
            answer = (
                f"Case {summary['case_number']} has {summary['total_wallets']} wallets with "
                f"average risk score of {summary['average_risk_score']}. "
                f"Risk distribution: {summary['risk_distribution']['critical']} critical, "
                f"{summary['risk_distribution']['medium']} medium, "
                f"{summary['risk_distribution']['low']} low. "
                f"{summary['attribution']['confirmed']} confirmed VASP attributions."
            )
            answer = await self._compose_answer(query, QueryType.RISK_SUMMARY, summary, answer)
            return AIResponse(
                answer=answer,
                query_type=QueryType.RISK_SUMMARY,
                confidence=ConfidenceLevel.HIGH_CONFIDENCE,
                evidence=[
                    Evidence(
                        source="case_aggregation",
                        evidence_type="statistical_summary",
                        description="Aggregated risk scores across all case wallets",
                        confidence=ConfidenceLevel.HIGH_CONFIDENCE,
                        data=summary,
                    )
                ],
                follow_up_questions=[
                    "Which wallets have the highest risk scores?",
                    "Show me the attribution summary for this case.",
                ],
            )

        return AIResponse(
            answer="Please specify a wallet ID or case ID for risk analysis.",
            query_type=QueryType.RISK_SUMMARY,
            confidence=ConfidenceLevel.UNKNOWN,
            evidence=[],
            follow_up_questions=["Provide a wallet ID or case number to analyze."],
        )

    async def _handle_attribution(
        self,
        query: str,
        case_id: Optional[str],
        wallet_id: Optional[str],
        address: Optional[str],
        chain: str,
    ) -> AIResponse:
        target_wallet_id = wallet_id
        target_address = address

        if not target_wallet_id and target_address:
            async with get_session() as session:
                from sqlalchemy import select
                from src.models import Wallet
                result = await session.execute(
                    select(Wallet).where(Wallet.address == target_address, Wallet.chain == chain)
                )
                wallet = result.scalar_one_or_none()
                if wallet:
                    target_wallet_id = str(wallet.id)
                    target_address = wallet.address

        if not target_wallet_id:
            return AIResponse(
                answer="Please specify a wallet address or ID for attribution analysis.",
                query_type=QueryType.ATTRIBUTION,
                confidence=ConfidenceLevel.UNKNOWN,
                evidence=[],
                follow_up_questions=["Provide a wallet address or ID to trace."],
            )

        attribution = await attribution_engine.get_attribution_summary(
            wallet_address=target_address or "",
            chain=chain,
        )

        if not attribution["attributed"]:
            answer = (
                f"No VASP attribution found for wallet {target_address or target_wallet_id} "
                f"within the current trace depth. The fund flow may not have reached a known "
                f"exchange, or the entity is not in our intelligence database."
            )
            confidence = ConfidenceLevel.UNKNOWN
        else:
            vasp = attribution["nearest_vasp"]
            answer = (
                f"Funds from wallet {target_address or target_wallet_id} trace to "
                f"**{vasp['entity_name']}** ({vasp['entity_type']}) with "
                f"{vasp['confidence']} confidence ({vasp['confidence_score']*100:.0f}%). "
                f"Distance: {vasp['distance_hops']} hops, Total value: {vasp['total_value_eth']:.4f} ETH. "
                f"Total attributions found: {attribution['summary']['exchanges_found']} exchanges, "
                f"{attribution['summary']['mixers_found']} mixers, "
                f"{attribution['summary']['bridges_found']} bridges."
            )
            confidence = ConfidenceLevel(vasp["confidence"])

        answer = await self._compose_answer(
            query, QueryType.ATTRIBUTION, {"wallet": target_address or target_wallet_id, **attribution}, answer
        )

        evidence = [
            Evidence(
                source="attribution_engine",
                evidence_type="graph_traversal_with_entity_intelligence",
                description=f"Shortest-path analysis to known entities with confidence propagation",
                confidence=confidence,
                data=attribution,
            )
        ]

        follow_up = [
            "Show me the full path to the nearest exchange.",
            "Are there any mixer interactions in the flow?",
            "What other entities were identified in the trace?",
        ]

        return AIResponse(
            answer=answer,
            query_type=QueryType.ATTRIBUTION,
            confidence=confidence,
            evidence=evidence,
            follow_up_questions=follow_up,
        )

    async def _handle_pattern_detection(
        self,
        query: str,
        case_id: Optional[str],
        wallet_id: Optional[str],
        address: Optional[str],
        chain: str,
    ) -> AIResponse:
        patterns_found = []

        if wallet_id:
            async with get_session() as session:
                from src.models import Wallet
                wallet = await session.get(Wallet, wallet_id)
                if wallet:
                    chain = wallet.chain
                    address = wallet.address

        if case_id:
            patterns = await graph_queries.detect_peel_chains(chain=chain)
            patterns_found.extend([{"type": "peel_chain", **p} for p in patterns])

            patterns = await graph_queries.detect_round_amount_patterns(chain=chain)
            patterns_found.extend([{"type": "round_amount", **p} for p in patterns])

            patterns = await graph_queries.detect_rapid_movement(chain=chain)
            patterns_found.extend([{"type": "rapid_movement", **p} for p in patterns])

        if not patterns_found:
            answer = f"No suspicious patterns detected on {chain} within the current analysis window."
            confidence = ConfidenceLevel.PROBABLE
        else:
            by_type = {}
            for p in patterns_found:
                t = p.get("type", "unknown")
                by_type[t] = by_type.get(t, 0) + 1

            answer = f"Detected {len(patterns_found)} suspicious patterns on {chain}: "
            answer += ", ".join([f"{count} {typ.replace('_', ' ')}" for typ, count in by_type.items()])
            answer += ". Top finding: "

            top = max(patterns_found, key=lambda x: x.get("total_value", 0) if isinstance(x, dict) else 0)
            answer += f"{top.get('type', 'unknown')} with {top.get('total_value', 'N/A')} ETH involved."

            confidence = ConfidenceLevel.HIGH_CONFIDENCE

        answer = await self._compose_answer(
            query,
            QueryType.PATTERN_DETECTION,
            {"chain": chain, "pattern_count": len(patterns_found), "patterns": patterns_found[:10]},
            answer,
        )

        evidence = [
            Evidence(
                source="graph_queries",
                evidence_type="pattern_detection_algorithms",
                description="Automated detection of peel chains, round amounts, rapid movement",
                confidence=confidence,
                data={"patterns": patterns_found[:10]},
            )
        ]

        follow_up = [
            "Show me the wallets involved in the peel chains.",
            "Which addresses have the most round-amount transactions?",
            "Generate a report on mixer interactions.",
        ]

        return AIResponse(
            answer=answer,
            query_type=QueryType.PATTERN_DETECTION,
            confidence=confidence,
            evidence=evidence,
            follow_up_questions=follow_up,
        )

    async def _handle_fund_flow(
        self,
        query: str,
        case_id: Optional[str],
        wallet_id: Optional[str],
        address: Optional[str],
        chain: str,
    ) -> AIResponse:
        if not wallet_id and not address:
            return AIResponse(
                answer="Please specify a wallet address or ID to trace fund flow.",
                query_type=QueryType.FUND_FLOW,
                confidence=ConfidenceLevel.UNKNOWN,
                evidence=[],
                follow_up_questions=["Provide a wallet address to trace."],
            )

        target_address = address
        if not target_address and wallet_id:
            async with get_session() as session:
                from src.models import Wallet
                wallet = await session.get(Wallet, wallet_id)
                if wallet:
                    target_address = wallet.address

        trace = await graph_repository.get_wallet_stats(target_address, chain)
        paths = await graph_repository.find_paths_to_entities(
            start_address=target_address,
            chain=chain,
            entity_types=[EntityType.EXCHANGE, EntityType.BRIDGE],
            max_depth=6,
            min_confidence=ConfidenceLevel.PROBABLE,
            limit=5,
        )

        if not trace:
            answer = f"No transaction data found for wallet {target_address} on {chain}."
            confidence = ConfidenceLevel.UNKNOWN
        else:
            answer = (
                f"Wallet {target_address} on {chain}: {trace.get('tx_count', 0)} transactions, "
                f"{trace.get('sent_count', 0)} sent, {trace.get('received_count', 0)} received. "
                f"Total sent: {trace.get('total_sent', 0):.4f} ETH, "
                f"Total received: {trace.get('total_received', 0):.4f} ETH. "
            )

            if paths:
                nearest = paths[0]
                answer += (
                    f"Nearest VASP: {nearest.endpoint_entity.name if nearest.endpoint_entity else 'Unknown'} "
                    f"({nearest.length} hops, {nearest.total_value:.4f} ETH). "
                )
            else:
                answer += "No VASP endpoint reached within trace depth. "

            confidence = ConfidenceLevel.HIGH_CONFIDENCE

        answer = await self._compose_answer(
            query,
            QueryType.FUND_FLOW,
            {
                "wallet": target_address,
                "chain": chain,
                "stats": trace,
                "paths_to_vasps": [
                    {
                        "endpoint_entity": p.endpoint_entity.name if p.endpoint_entity else None,
                        "hops": p.length,
                        "total_value_eth": p.total_value,
                    }
                    for p in paths
                ],
            },
            answer,
        )

        evidence = [
            Evidence(
                source="graph_repository",
                evidence_type="wallet_statistics_and_pathfinding",
                description="Transaction statistics and Dijkstra shortest-path to entities",
                confidence=confidence,
                data={"trace": trace, "paths_found": len(paths)},
            )
        ]

        follow_up = [
            "Show me the transaction timeline for this wallet.",
            "What entities are reachable within 3 hops?",
            "Are there any cross-chain bridge interactions?",
        ]

        return AIResponse(
            answer=answer,
            query_type=QueryType.FUND_FLOW,
            confidence=confidence,
            evidence=evidence,
            follow_up_questions=follow_up,
        )

    async def _handle_entity_lookup(
        self,
        query: str,
        case_id: Optional[str],
        wallet_id: Optional[str],
        address: Optional[str],
        chain: str,
    ) -> AIResponse:
        if not address:
            return AIResponse(
                answer="Please provide an address to look up.",
                query_type=QueryType.ENTITY_LOOKUP,
                confidence=ConfidenceLevel.UNKNOWN,
                evidence=[],
                follow_up_questions=["Provide an Ethereum address to look up."],
            )

        entity = await graph_repository.get_wallet(address, chain)

        if not entity:
            from src.intelligence import entity_intelligence
            entity = await entity_intelligence.lookup_entity(address, chain)

        if not entity:
            answer = f"No entity information found for {address} on {chain}."
            confidence = ConfidenceLevel.UNKNOWN
        else:
            answer = (
                f"Address: {address}\n"
                f"Chain: {chain}\n"
                f"Label: {entity.label or 'None'}\n"
                f"Risk Score: {entity.risk_score}/100\n"
            )
            if hasattr(entity, 'entity_name') and entity.entity_name:
                answer += f"Entity: {entity.entity_name} ({entity.entity_type.value if entity.entity_type else 'Unknown'})\n"
                answer += f"Confidence: {entity.entity_confidence.value if entity.entity_confidence else 'Unknown'}"
            confidence = ConfidenceLevel.HIGH_CONFIDENCE

        entity_context = entity.to_dict() if hasattr(entity, "to_dict") else {}
        answer = await self._compose_answer(
            query, QueryType.ENTITY_LOOKUP, {"address": address, "chain": chain, "entity": entity_context}, answer
        )

        evidence = [
            Evidence(
                source="graph_repository",
                evidence_type="entity_registry_lookup",
                description="Direct entity registry query",
                confidence=confidence,
                data=entity.to_dict() if hasattr(entity, 'to_dict') else {},
            )
        ]

        return AIResponse(
            answer=answer,
            query_type=QueryType.ENTITY_LOOKUP,
            confidence=confidence,
            evidence=evidence,
            follow_up_questions=["Show me the transaction history for this address."],
        )

    async def _handle_case_overview(
        self,
        query: str,
        case_id: Optional[str],
        wallet_id: Optional[str],
        address: Optional[str],
        chain: str,
    ) -> AIResponse:
        if not case_id:
            return AIResponse(
                answer="Please specify a case ID or case number for overview.",
                query_type=QueryType.CASE_OVERVIEW,
                confidence=ConfidenceLevel.UNKNOWN,
                evidence=[],
                follow_up_questions=["Provide a case number (e.g., TRX-20240115-0042)."],
            )

        async with get_session() as session:
            case = await session.get(Case, case_id)
            if not case:
                return AIResponse(
                    answer=f"Case {case_id} not found.",
                    query_type=QueryType.CASE_OVERVIEW,
                    confidence=ConfidenceLevel.UNKNOWN,
                    evidence=[],
                    follow_up_questions=[],
                )

            from sqlalchemy import select
            from src.models import Wallet, InvestigationRun
            wallets_result = await session.execute(select(Wallet).where(Wallet.case_id == case_id))
            wallets = list(wallets_result.scalars().all())

            inv_result = await session.execute(select(InvestigationRun).where(InvestigationRun.case_id == case_id))
            investigations = list(inv_result.scalars().all())

        completed = len([i for i in investigations if i.status == "completed"])
        running = len([i for i in investigations if i.status == "running"])
        high_risk = len([w for w in wallets if float(w.risk_score or 0) >= 75])

        answer = (
            f"**Case {case.case_number}: {case.title}**\n"
            f"Type: {case.crime_type.replace('_', ' ').title()}\n"
            f"Status: {case.status.replace('_', ' ').title()}\n"
            f"Wallets: {len(wallets)} | Investigations: {len(investigations)} "
            f"({completed} completed, {running} running)\n"
            f"High-risk wallets: {high_risk}\n"
            f"Chains: {', '.join(set(w.chain for w in wallets))}\n"
        )

        case_context = {
            "case_number": case.case_number,
            "title": case.title,
            "crime_type": case.crime_type,
            "status": case.status,
            "wallet_count": len(wallets),
            "investigation_count": len(investigations),
            "completed_investigations": completed,
            "running_investigations": running,
            "high_risk_wallets": high_risk,
            "chains": list(set(w.chain for w in wallets)),
        }
        answer = await self._compose_answer(query, QueryType.CASE_OVERVIEW, case_context, answer)

        evidence = [
            Evidence(
                source="database",
                evidence_type="case_aggregation",
                description="Aggregated case statistics from PostgreSQL",
                confidence=ConfidenceLevel.CONFIRMED,
                data={
                    "case_id": str(case.id),
                    "wallet_count": len(wallets),
                    "investigation_count": len(investigations),
                },
            )
        ]

        follow_up = [
            "Show me the risk distribution for this case.",
            "List all wallets with their attribution status.",
            "What are the top risk factors across this case?",
        ]

        return AIResponse(
            answer=answer,
            query_type=QueryType.CASE_OVERVIEW,
            confidence=ConfidenceLevel.CONFIRMED,
            evidence=evidence,
            follow_up_questions=follow_up,
        )

    async def _handle_timeline(
        self,
        query: str,
        case_id: Optional[str],
        wallet_id: Optional[str],
        address: Optional[str],
        chain: str,
    ) -> AIResponse:
        if not wallet_id and not address:
            return AIResponse(
                answer="Please specify a wallet for timeline analysis.",
                query_type=QueryType.TIMELINE,
                confidence=ConfidenceLevel.UNKNOWN,
                evidence=[],
                follow_up_questions=["Provide a wallet address or ID."],
            )

        target_address = address
        if wallet_id:
            async with get_session() as session:
                from src.models import Wallet
                wallet = await session.get(Wallet, wallet_id)
                if wallet:
                    target_address = wallet.address
                    chain = wallet.chain

        flow = await graph_queries.get_temporal_flow(
            address=target_address,
            chain=chain,
            start_date=datetime(2020, 1, 1),
            end_date=datetime.utcnow(),
            bucket="day",
        )

        if not flow:
            answer = f"No transaction timeline found for {target_address} on {chain}."
            confidence = ConfidenceLevel.UNKNOWN
        else:
            total_days = len(flow)
            active_days = len([d for d in flow if d.get("tx_count", 0) > 0])
            total_txs = sum(d.get("tx_count", 0) for d in flow)

            answer = (
                f"Timeline for {target_address} on {chain}: {total_days} days analyzed, "
                f"{active_days} active days, {total_txs} total transactions. "
            )

            if flow:
                peak = max(flow, key=lambda d: d.get("tx_count", 0))
                answer += f"Peak activity: {peak.get('bucket', 'N/A')} with {peak.get('tx_count', 0)} transactions."

            confidence = ConfidenceLevel.HIGH_CONFIDENCE

        answer = await self._compose_answer(
            query,
            QueryType.TIMELINE,
            {"wallet": target_address, "chain": chain, "daily_flow": flow[:60]},
            answer,
        )

        evidence = [
            Evidence(
                source="graph_queries",
                evidence_type="temporal_flow_analysis",
                description="Daily transaction volume bucketing",
                confidence=confidence,
                data={"data_points": len(flow)},
            )
        ]

        return AIResponse(
            answer=answer,
            query_type=QueryType.TIMELINE,
            confidence=confidence,
            evidence=evidence,
            follow_up_questions=["Show me the largest transactions in this period."],
        )

    async def _handle_comparison(
        self,
        query: str,
        case_id: Optional[str],
        wallet_id: Optional[str],
        address: Optional[str],
        chain: str,
    ) -> AIResponse:
        answer = "Comparison analysis requires two wallets or cases to compare. Please specify both."
        confidence = ConfidenceLevel.UNKNOWN
        evidence = []

        return AIResponse(
            answer=answer,
            query_type=QueryType.COMPARISON,
            confidence=confidence,
            evidence=evidence,
            follow_up_questions=["Provide two wallet IDs or case numbers to compare."],
        )

    async def _handle_general(
        self,
        query: str,
        case_id: Optional[str],
        wallet_id: Optional[str],
        address: Optional[str],
        chain: str,
    ) -> AIResponse:
        answer = (
            "I can help you with:\n"
            "- **Risk analysis**: 'What's the risk score for wallet 0x...?'\n"
            "- **Attribution**: 'Where did funds from 0x... go?'\n"
            "- **Patterns**: 'Any suspicious patterns on Ethereum?'\n"
            "- **Fund flow**: 'Trace the money from wallet 0x...'\n"
            "- **Entity lookup**: 'Who owns address 0x...?'\n"
            "- **Case overview**: 'Tell me about case TRX-20240115-0042'\n"
            "- **Timeline**: 'Show me transaction history for wallet 0x...'\n\n"
            "Please ask a specific question about a wallet, case, or investigation."
        )

        return AIResponse(
            answer=answer,
            query_type=QueryType.CASE_OVERVIEW,
            confidence=ConfidenceLevel.UNKNOWN,
            evidence=[],
            follow_up_questions=[
                "What's the risk score for a specific wallet?",
                "Trace funds from a suspect address",
                "Show me case summary",
            ],
        )

    async def _get_wallet_risk(self, wallet_id: str):
        async with get_session() as session:
            from src.models import Wallet, Transaction
            from sqlalchemy import select
            wallet = await session.get(Wallet, wallet_id)
            if not wallet:
                return None

            result = await session.execute(
                select(Transaction).where(Transaction.wallet_id == wallet_id)
            )
            transactions = result.scalars().all()

            graph_wallet = type('GraphWallet', (), {
                'address': wallet.address,
                'chain': wallet.chain,
                'label': wallet.label,
                'risk_score': float(wallet.risk_score or 0),
                'first_seen': wallet.created_at,
                'last_seen': wallet.updated_at,
                'tx_count': len(transactions),
            })()

            graph_transactions = []
            for tx in transactions:
                graph_transactions.append(type('GraphTransaction', (), {
                    'tx_hash': tx.tx_hash,
                    'block_number': tx.block_number,
                    'timestamp': tx.timestamp,
                    'from_address': tx.from_address,
                    'to_address': tx.to_address,
                    'value': tx.value,
                    'value_usd': tx.value_usd,
                    'token_address': tx.token_address,
                    'token_symbol': tx.token_symbol,
                    'method': tx.method,
                    'is_suspicious': tx.is_suspicious,
                })())

            graph_context = {}
            try:
                graph_context["mixer_interactions"] = await graph_queries.find_mixer_interactions(
                    address=wallet.address, chain=wallet.chain, max_hops=4
                )
                graph_context["peel_chains"] = await graph_queries.detect_peel_chains(chain=wallet.chain)
            except Exception:
                pass

            entity_data = None
            if wallet.entity_name:
                entity_data = {
                    "entity_name": wallet.entity_name,
                    "entity_type": wallet.entity_type,
                    "confidence": wallet.entity_confidence,
                }

            return await risk_scoring_engine.assess_wallet(
                wallet=graph_wallet,
                transactions=graph_transactions,
                entity_data=entity_data,
                graph_context=graph_context,
            )

    async def _get_case_risk_summary(self, case_id: str) -> Dict[str, Any]:
        async with get_session() as session:
            case = await session.get(Case, case_id)
            if not case:
                return {}

            from sqlalchemy import select
            from src.models import Wallet
            result = await session.execute(select(Wallet).where(Wallet.case_id == case_id))
            wallets = list(result.scalars().all())

        high_risk = len([w for w in wallets if float(w.risk_score or 0) >= 75])
        medium_risk = len([w for w in wallets if 40 <= float(w.risk_score or 0) < 75])
        low_risk = len([w for w in wallets if 20 <= float(w.risk_score or 0) < 40])
        info_risk = len([w for w in wallets if float(w.risk_score or 0) < 20])

        attributed = [w for w in wallets if w.entity_name and w.entity_confidence in ["CONFIRMED", "HIGH_CONFIDENCE"]]
        probable = [w for w in wallets if w.entity_name and w.entity_confidence == "PROBABLE"]

        return {
            "case_id": str(case.id),
            "case_number": case.case_number,
            "total_wallets": len(wallets),
            "chains": list(set(w.chain for w in wallets)),
            "risk_distribution": {
                "critical": high_risk,
                "high": 0,
                "medium": medium_risk,
                "low": low_risk,
                "info": info_risk,
            },
            "attribution": {
                "confirmed": len(attributed),
                "probable": len(probable),
                "unattributed": len(wallets) - len(attributed) - len(probable),
            },
            "average_risk_score": round(sum(float(w.risk_score or 0) for w in wallets) / len(wallets), 1) if wallets else 0,
        }

    async def generate_narrative(
        self,
        case_summary: Dict[str, Any],
        wallets_summary: List[Dict[str, Any]],
        findings: Dict[str, Any],
        fallback_narrative: str,
    ) -> str:
        """Generate an investigation narrative via Claude over structured case data.

        Graceful degradation (non-negotiable): with no ANTHROPIC_API_KEY configured,
        or on any API failure, this returns the deterministic markdown template the
        caller already built - never raises, never turns into a 500.
        """
        if not self._client:
            return fallback_narrative

        try:
            narrative_system_prompt = (
                "You are the TRACE-X AI Assistant, writing an investigation narrative "
                "report for a blockchain financial-crimes case. You are given the case "
                "metadata, a summary of the analyzed wallets, and key findings as "
                "structured JSON. Use ONLY the data provided - never invent addresses, "
                "amounts, or entity names. Write a professional markdown report with "
                "these sections: '# Investigation Narrative: <case title>', "
                "'## Executive Summary', '## Wallet Analysis' (a bulleted list of the "
                "most notable wallets), '## Key Findings', and '## Recommendations' "
                "(actionable next steps for the investigating team). Close with a note "
                "that this narrative is AI-generated from automated analysis and "
                "human review is recommended for legal proceedings."
            )
            payload = {
                "case": case_summary,
                "wallets": wallets_summary,
                "findings": findings,
            }
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=narrative_system_prompt,
                messages=[{"role": "user", "content": json.dumps(payload, default=str)}],
            )
            text = next((b.text for b in response.content if b.type == "text"), "")
            return text.strip() or fallback_narrative
        except Exception as e:
            self.logger.warning("llm_generate_narrative_failed", error=str(e))
            return fallback_narrative

    async def _resolve_case_id(self, case_number: str) -> Optional[str]:
        async with get_session() as session:
            from sqlalchemy import select
            from src.models import Case
            result = await session.execute(select(Case).where(Case.case_number == case_number))
            case = result.scalar_one_or_none()
            return str(case.id) if case else None


investigation_assistant = InvestigationAssistant()