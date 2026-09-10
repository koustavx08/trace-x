"""
Anthropic AI provider.

Wraps the existing Anthropic client usage from InvestigationAssistant.
"""

import json
from typing import Any

import anthropic
import structlog

from ...core.config import get_settings
from ..schemas import QueryType
from .base import AIProvider

logger = structlog.get_logger(__name__)

#: System prompt used for classification tool calls.
#: Defined locally to avoid circular import with service.py
CLASSIFY_SYSTEM_PROMPT = (
    "Classify the investigator's query and extract any entities "
    "mentioned. Always call the classify_investigation_query tool."
)

#: Tool schema for classification - defined locally to avoid circular import
#: with service.py (which imports from providers.anthropic)
CLASSIFY_TOOL = {
    "name": "classify_investigation_query",
    "description": "Classify the investigator's query and extract entities",
    "input_schema": {
        "type": "object",
        "properties": {
            "query_type": {"type": "string"},
            "entities": {"type": "object"},
        },
        "required": ["query_type"],
        "additionalProperties": False,
    },
}


class AnthropicProvider(AIProvider):
    """
    Anthropic provider for AI services.

    Wraps the existing Anthropic client usage from the InvestigationAssistant.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.ANTHROPIC_API_KEY
        self._model = model if model is not None else settings.ANTHROPIC_MODEL
        self.model_name = self._model

        if not self._api_key:
            self._client = None
        else:
            self._client = anthropic.AsyncAnthropic(api_key=self._api_key)

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def is_configured(self) -> bool:
        return self._client is not None

    def _require_client(self) -> "anthropic.AsyncAnthropic":
        """Return the client, asserting it is configured.

        `is_configured()` guards every call site, but a bool-returning method
        tells the type checker nothing -- so `self._client.messages` read as
        `None.messages`. Callers are all inside `try/except Exception` blocks
        that fall back gracefully, so the raise here is unreachable in practice.
        """
        if self._client is None:
            raise RuntimeError("AnthropicProvider used without an API key configured")
        return self._client

    async def classify_and_extract(self, query: str) -> dict[str, Any] | None:
        """
        Structured intent classification + entity extraction via Anthropic tool-use.

        Returns None (never raises) if the client isn't configured or the call
        fails for any reason - callers must fall back to the regex-based
        classify_query()/extract_entities() in that case.
        """
        if not self.is_configured():
            return None
        try:
            response = await self._require_client().messages.create(
                model=self._model,
                max_tokens=256,
                system=(
                    "Classify the investigator's query and extract any entities "
                    "mentioned. Always call the classify_investigation_query tool."
                ),
                tools=[CLASSIFY_TOOL],
                tool_choice={"type": "tool", "name": "classify_investigation_query"},
                messages=[{"role": "user", "content": query}],
            )  # type: ignore[call-overload]
            self._record_success()
            for block in response.content:
                if isinstance(block, anthropic.types.ToolUseBlock):
                    return dict(block.input)  # type: ignore[arg-type]
        except Exception as e:
            self._record_failure(e)
            logger.warning("anthropic_classify_failed", error=str(e))
        return None

    async def compose_answer(
        self,
        query: str,
        query_type: QueryType,
        context: dict[str, Any],
        fallback_answer: str,
    ) -> str:
        """
        Turn gathered evidence into a natural-language answer via Anthropic.

        Graceful degradation: if the Anthropic client isn't configured, or the API
        call fails/times out for any reason, this returns the deterministic template
        answer that the caller already built - never lets a missing key or a transient
        API error surface as a 500 to the investigator.
        """
        if not self.is_configured():
            return fallback_answer

        try:
            payload = {
                "investigator_query": query,
                "intent": query_type.value,
                "context": context,
            }
            # Use a default system prompt for composition since SYSTEM_PROMPT
            # is defined locally to avoid circular imports
            system_prompt = (
                "You are the TRACE-X AI Assistant, turning investigation evidence "
                "into a natural-language answer. Be concise and factual. Use the "
                "provided context to compose a clear answer to the investigator's query."
            )
            response = await self._require_client().messages.create(
                model=self._model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": json.dumps(payload, default=str)}],
            )
            self._record_success()
            text = next(
                (b.text for b in response.content if isinstance(b, anthropic.types.TextBlock)),
                "",
            )
            return text.strip() or fallback_answer
        except Exception as e:
            self._record_failure(e)
            logger.warning(
                "anthropic_compose_answer_failed", error=str(e), query_type=query_type.value
            )
            return fallback_answer

    async def generate_narrative(
        self,
        case_summary: dict[str, Any],
        wallets_summary: list[dict[str, Any]],
        findings: dict[str, Any],
        fallback_narrative: str,
    ) -> str:
        """
        Generate an investigation narrative via Anthropic over structured case data.

        Graceful degradation: with no ANTHROPIC_API_KEY configured, or on any API
        failure, this returns the deterministic markdown template the caller already
        built - never raises, never turns into a 500.
        """
        if not self.is_configured():
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
            response = await self._require_client().messages.create(
                model=self._model,
                max_tokens=2048,
                system=narrative_system_prompt,
                messages=[{"role": "user", "content": json.dumps(payload, default=str)}],
            )
            self._record_success()
            text = next(
                (b.text for b in response.content if isinstance(b, anthropic.types.TextBlock)),
                "",
            )
            return text.strip() or fallback_narrative
        except Exception as e:
            self._record_failure(e)
            logger.warning("anthropic_generate_narrative_failed", error=str(e))
            return fallback_narrative

    async def close(self) -> None:
        # Anthropic client doesn't have a close method, but we implement for interface consistency
        pass
