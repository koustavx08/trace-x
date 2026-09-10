from abc import ABC, abstractmethod
from typing import Any

from ..schemas import QueryType


class AIProvider(ABC):
    """Abstract base class for AI providers.

    Every `compose_*` method here is defined to return a template fallback
    when the live call fails, which is the right behaviour for a request --
    an investigator gets an answer built from real evidence instead of an
    error. It is the wrong behaviour for *reporting*: a provider whose every
    call is failing looked identical to one that was working, and
    `GET /ai/capabilities` went on describing the deployment as live.

    Subclasses that make a network call record the outcome through
    `_record_success` / `_record_failure`, so the degraded state is visible
    without having to read the logs.
    """

    #: Model identifier this provider talks to, or None for providers that
    #: make no model call at all (the template and disabled providers).
    model_name: str | None = None

    #: Reason the most recent live call failed, cleared by the next success.
    last_error: str | None = None

    def _record_success(self) -> None:
        self.last_error = None

    def _record_failure(self, error: Exception) -> None:
        self.last_error = f"{type(error).__name__}: {error}"

    @property
    def degraded(self) -> bool:
        """True when live calls are failing and answers are templates."""
        return self.last_error is not None

    @abstractmethod
    async def classify_and_extract(self, query: str) -> dict[str, Any] | None:
        """Classify the query and extract entities.

        Returns None if unable to classify (caller should fall back to regex).
        """
        pass

    @abstractmethod
    async def compose_answer(
        self,
        query: str,
        query_type: QueryType,
        context: dict[str, Any],
        fallback_answer: str,
    ) -> str:
        """Compose a natural language answer from structured context.

        Returns the composed answer, or the fallback answer if unable to compose.
        """
        pass

    @abstractmethod
    async def generate_narrative(
        self,
        case_summary: dict[str, Any],
        wallets_summary: list[dict[str, Any]],
        findings: dict[str, Any],
        fallback_narrative: str,
    ) -> str:
        """Generate an investigation narrative from structured data.

        Returns the generated narrative, or the fallback narrative if unable to generate.
        """
        pass
