"""
Disabled AI provider.

Returns a fixed message indicating that AI assistance is disabled.
"""
from typing import Any, Dict, Optional

import structlog

from .base import AIProvider
from ..schemas import QueryType

logger = structlog.get_logger(__name__)


class DisabledProvider(AIProvider):
    """Provider that returns a fixed message when AI is disabled."""

    def __init__(self):
        pass

    @property
    def provider_name(self) -> str:
        return "disabled"

    def is_configured(self) -> bool:
        # This provider is always "configured" in the sense that it exists.
        return True

    async def classify_and_extract(self, query: str) -> Optional[Dict[str, Any]]:
        """Return None to fall back to regex classification."""
        return None

    async def compose_answer(
        self,
        query: str,
        query_type: QueryType,
        context: Dict[str, Any],
        fallback_answer: str,
    ) -> str:
        """Return the disabled message."""
        return (
            "AI assistance is currently disabled on this deployment "
            "(AI_MODE=disabled). The rest of TRACE-X - risk scoring, "
            "attribution, graph analysis, and reporting - is unaffected."
        )

    async def generate_narrative(
        self,
        case_summary: Dict[str, Any],
        wallets_summary: list[Dict[str, Any]],
        findings: Dict[str, Any],
        fallback_narrative: str,
    ) -> str:
        """Return a fixed message indicating narrative generation is disabled."""
        return (
            "AI assistance is currently disabled on this deployment "
            "(AI_MODE=disabled). Narrative generation is unavailable."
        )

    async def close(self) -> None:
        pass