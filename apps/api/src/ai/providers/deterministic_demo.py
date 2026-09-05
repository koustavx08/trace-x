"""
Deterministic demo AI provider.

Provides deterministic, template-based responses (the current fallback behavior).
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import structlog

from .schemas import QueryType

logger = structlog.get_logger(__name__)


@dataclass
class Evidence:
    source: str
    evidence_type: str
    description: str
    confidence: ConfidenceLevel
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class DeterministicDemoProvider:
    """
    Deterministic demo provider that uses regex-based classification and template answers.
    This mimics the current behavior when ANTHROPIC_API_KEY is not set.
    """

    def __init__(self):
        self._query_patterns = self._compile_patterns()

    @property
    def provider_name(self) -> str:
        return "deterministic_demo"

    def is_configured(self) -> bool:
        # This provider is always available.
        return True

    def _compile_patterns(self) -> dict[QueryType, list[re.Pattern]]:
        return {
            QueryType.RISK_SUMMARY: [
                re.compile(r"(risk|score|danger|threat).*(wallet|address)", re.I),
                re.compile(r"how risky|risk level|risk assessment", re.I),
            ],
            QueryType.ATTRIBUTION: [
                re.compile(r"(attribut|vasp|exchange|where.*go|endpoint)", re.I),
                re.compile(r"(cash out|off.ramp|deposit to)", re.I),
            ],
            QueryType.PATTERN_DETECTION: [
                re.compile(r"(pattern|peel.chain|round.amount|rapid|mixer|structur)", re.I),
                re.compile(r"(suspicious|anomal|unusual).*(transaction|flow|movement)", re.I),
            ],
            QueryType.FUND_FLOW: [
                re.compile(
                    r"(flow|trace|path|hop|movement|transfer).*(fund|money|eth|value)", re.I
                ),
                re.compile(r"(where did|where.*from|where.*to|follow the money)", re.I),
            ],
            QueryType.ENTITY_LOOKUP: [
                re.compile(r"(who is|who owns|what is|entity|owner|label).*(address|wallet)", re.I),
                re.compile(r"(known|identified|label).*(address|wallet)", re.I),
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

    async def classify_and_extract(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Use regex-based classification and entity extraction.

        Returns a dict with the classification and entities, or None if unable to classify.
        Note: This provider always returns a classification (at least CASE_OVERVIEW) and entities.
        """
        matched_type = self._match_query_type(query)
        query_type = matched_type or QueryType.CASE_OVERVIEW
        entities = self.extract_entities(query)

        # Always return a dict, even if no entities are found.
        result = {"query_type": query_type.value}
        result.update(entities)
        # Remove empty entities? We'll keep them as empty strings? No, we'll only add if present.
        # But note: the caller expects the same format as the LLM extraction.
        # We'll return the dict as is.
        return result

    async def compose_answer(
        self,
        query: str,
        query_type: QueryType,
        context: Dict[str, Any],
        fallback_answer: str,
    ) -> str:
        """
        In deterministic demo mode, we do not attempt to compose an answer.
        We return the fallback answer that the caller has already built.
        """
        return fallback_answer

    async def generate_narrative(
        self,
        case_summary: Dict[str, Any],
        wallets_summary: list[Dict[str, Any]],
        findings: Dict[str, Any],
        fallback_narrative: str,
    ) -> str:
        """
        In deterministic demo mode, we do not attempt to generate a narrative.
        We return the fallback narrative that the caller has already built.
        """
        return fallback_narrative

    async def close(self) -> None:
        pass