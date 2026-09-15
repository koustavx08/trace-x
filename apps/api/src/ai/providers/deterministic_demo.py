"""
Deterministic demo AI provider.

Provides deterministic, template-based responses (the current fallback behavior).
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

from ..schemas import ConfidenceLevel, QueryType
from .base import AIProvider

logger = structlog.get_logger(__name__)


@dataclass
class Evidence:
    source: str
    evidence_type: str
    description: str
    confidence: ConfidenceLevel
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DeterministicDemoProvider(AIProvider):
    """
    Deterministic demo provider that uses regex-based classification and template answers.
    This mimics the current behavior when ANTHROPIC_API_KEY is not set.
    """

    def __init__(self):
        self._query_patterns: dict[QueryType, list[re.Pattern]] = self._compile_patterns()

    @property
    def provider_name(self) -> str:
        return "deterministic_demo"

    def is_configured(self) -> bool:
        # This provider is always available.
        return True

    def _compile_patterns(self) -> dict[QueryType, list[re.Pattern]]:
        return {
            QueryType.RISK_SUMMARY: [
                re.compile(r"(risk|score|danger|threat).*(wallet|address|node|factors|0x)", re.I),
                re.compile(
                    r"how risky|risk level|risk assessment|risk factor|risk breakdown|risk table",
                    re.I,
                ),
            ],
            QueryType.ATTRIBUTION: [
                re.compile(
                    r"(attribut|vasp|exchange|where.*go|endpoint|hop).*(wallet|address|node)?", re.I
                ),
                re.compile(r"(cash out|off.ramp|deposit to)", re.I),
            ],
            QueryType.PATTERN_DETECTION: [
                re.compile(r"(pattern|peel.chain|round.amount|rapid|mixer|structur)", re.I),
                re.compile(r"(suspicious|anomal|unusual).*(transaction|flow|movement)", re.I),
            ],
            QueryType.FUND_FLOW: [
                re.compile(
                    r"(flow|trace|path|hop|movement|transfer).*(fund|money|eth|value|node)", re.I
                ),
                re.compile(r"(where did|where.*from|where.*to|follow the money)", re.I),
            ],
            QueryType.ENTITY_LOOKUP: [
                re.compile(
                    r"(who is|who owns|what is|entity|owner|label).*(address|wallet|node)", re.I
                ),
                re.compile(r"(known|identified|label).*(address|wallet|node)", re.I),
            ],
            QueryType.CASE_OVERVIEW: [
                re.compile(r"(case|investigation).*(summary|overview|status|progress)", re.I),
                re.compile(r"(tell me about|describe).*(case|investigation)", re.I),
            ],
            QueryType.TIMELINE: [
                re.compile(
                    r"(timeline|when|chronolog|history|sequence).*(transaction|event)", re.I
                ),
                re.compile(r"(transaction|event).*(timeline|chronolog|history|sequence)", re.I),
                re.compile(r"(first|last|recent).*(transaction|activity)", re.I),
            ],
            QueryType.COMPARISON: [
                re.compile(r"(compar|versus|vs|difference).*(wallet|case|risk)", re.I),
                re.compile(r"(better|worse|higher|lower).*(risk|score)", re.I),
            ],
        }

    def _match_query_type(self, query: str) -> QueryType | None:
        """Returns the matched QueryType, or None if no pattern matched."""
        for query_type, patterns in self._query_patterns.items():
            for pattern in patterns:
                if pattern.search(query):
                    return query_type
        return None

    def extract_entities(self, query: str) -> dict[str, Any]:
        entities = {}

        # 1. 66-character transaction hash (0x + 64 hex characters)
        tx_match = re.search(r"(0x[a-fA-F0-9]{64})", query, re.I)
        if tx_match:
            entities["tx_hash"] = tx_match.group(1)

        # 2. 42-character address (0x + 40 hex characters)
        address_match = re.search(r"(0x[a-fA-F0-9]{40})(?![a-fA-F0-9])", query, re.I)
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

    async def classify_and_extract(self, query: str) -> dict[str, Any] | None:
        """
        Use regex-based classification and entity extraction.

        Returns a dict with the classification and entities, or None if unable to classify.
        Note: This provider always returns a classification (at least CASE_OVERVIEW) and entities.
        """
        matched_type = self._match_query_type(query)
        if matched_type is None:
            return None

        result = {"query_type": matched_type.value}
        result.update(self.extract_entities(query))
        return result

    async def compose_answer(
        self,
        query: str,
        query_type: QueryType,
        context: dict[str, Any],
        fallback_answer: str,
    ) -> str:
        """
        In deterministic demo mode, return the fallback answer, enhanced with
        a structured markdown risk factor table if factor details are available.
        """
        if query_type == QueryType.RISK_SUMMARY and "factors" in context and context["factors"]:
            table_lines = [
                fallback_answer,
                "",
                "### Forensic Risk Factor Breakdown",
                "| Risk Factor | Severity | Base Score | Weight | Weighted Score | On-Chain Evidence & Detail |",
                "| :--- | :---: | :---: | :---: | :---: | :--- |",
            ]
            for f in context["factors"]:
                factor_name = f.get("factor", "").replace("_", " ").title()
                severity = str(f.get("severity", "")).upper()
                score = f.get("score", 0)
                weight = f.get("weight", 0)
                weighted = f.get("weighted_score", 0)
                desc = f.get("description", "")
                table_lines.append(
                    f"| **{factor_name}** | `{severity}` | {score} | {weight} | **+{weighted:.2f}** | {desc} |"
                )
            overall = context.get("overall_score", 0)
            level = str(context.get("risk_level", "")).upper()
            table_lines.append(
                f"| **OVERALL** | `{level}` | — | — | **{overall:.1f}/100** | *Weighted sum with 10% co-occurrence compounding* |"
            )
            return "\n".join(table_lines)

        return fallback_answer

    async def generate_narrative(
        self,
        case_summary: dict[str, Any],
        wallets_summary: list[dict[str, Any]],
        findings: dict[str, Any],
        fallback_narrative: str,
    ) -> str:
        """
        In deterministic demo mode, we do not attempt to generate a narrative.
        We return the fallback narrative that the caller has already built.
        """
        return fallback_narrative

    async def close(self) -> None:
        pass
