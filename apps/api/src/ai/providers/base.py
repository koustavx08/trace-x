from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..schemas import ConfidenceLevel, QueryType


class AIProvider(ABC):
    """Abstract base class for AI providers."""

    @abstractmethod
    async def classify_and_extract(self, query: str) -> Optional[Dict[str, Any]]:
        """Classify the query and extract entities.

        Returns None if unable to classify (caller should fall back to regex).
        """
        pass

    @abstractmethod
    async def compose_answer(
        self,
        query: str,
        query_type: QueryType,
        context: Dict[str, Any],
        fallback_answer: str,
    ) -> str:
        """Compose a natural language answer from structured context.

        Returns the composed answer, or the fallback answer if unable to compose.
        """
        pass

    @abstractmethod
    async def generate_narrative(
        self,
        case_summary: Dict[str, Any],
        wallets_summary: list[Dict[str, Any]],
        findings: Dict[str, Any],
        fallback_narrative: str,
    ) -> str:
        """Generate an investigation narrative from structured data.

        Returns the generated narrative, or the fallback narrative if unable to generate.
        """
        pass