"""
OpenRouter AI provider.

Implements the AIProvider interface using the OpenRouter API (OpenAI-compatible).
"""

import json
from typing import Any

import httpx
import structlog

from ...core.config import get_settings
from ..schemas import QueryType
from .base import AIProvider

logger = structlog.get_logger(__name__)


def _message_text(data: dict[str, Any]) -> str:
    """Pull the assistant text out of an OpenAI-shaped completion.

    `content` is not always a string. A model that answers entirely from a
    reasoning block, or that is cut off by the token limit, returns
    `"content": null`, and indexing straight into `.strip()` raised
    AttributeError -- which the callers turned into a silent template answer.
    Some models also return content as a list of typed parts rather than a
    plain string.
    """
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")

    if isinstance(content, list):
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not content:
        # Reasoning models put the answer here when they emit no content block.
        content = message.get("reasoning") or ""
    return str(content).strip()


class OpenRouterProvider(AIProvider):
    """
    OpenRouter provider for AI services.

    Uses the OpenRouter API (https://openrouter.ai) which is OpenAI-compatible.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 15.0,
    ):
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.OPENROUTER_API_KEY
        self._base_url = base_url if base_url is not None else settings.OPENROUTER_BASE_URL
        self._model = model if model is not None else settings.OPENROUTER_MODEL
        self.model_name = self._model

        # Only initialize HTTP client if we have both required fields
        self._http_client: httpx.AsyncClient | None
        if self._api_key and self._model:
            self._http_client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=timeout,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        else:
            self._http_client = None

    @property
    def provider_name(self) -> str:
        return "openrouter"

    def is_configured(self) -> bool:
        return bool(self._api_key and self._model)

    def _require_http_client(self) -> httpx.AsyncClient:
        """Return the HTTP client, asserting it was constructed.

        `is_configured()` guards every call site but narrows nothing for the
        type checker. All callers sit inside `try/except Exception` blocks that
        fall back, so the raise is unreachable in practice.
        """
        if self._http_client is None:
            raise RuntimeError("OpenRouterProvider used without an API key/model configured")
        return self._http_client

    async def classify_and_extract(self, query: str) -> dict[str, Any] | None:
        """
        Classify the query and extract entities using OpenRouter.

        Returns None if unable to classify (caller should fall back to regex).
        """
        if not self.is_configured():
            return None

        try:
            # We'll use the OpenRouter chat completion with a prompt that instructs
            # the model to return a JSON object matching the CLASSIFY_TOOL schema.
            # Note: We are not using the tool use feature of OpenAI because not all
            # models on OpenRouter support it. Instead, we prompt for JSON.
            system_prompt = (
                "Classify the investigator's query and extract any entities "
                "mentioned. Return a JSON object matching the following schema: "
                + json.dumps(
                    {
                        "query_type": {
                            "enum": [qt.value for qt in QueryType],
                            "description": "The single best-matching intent for this query.",
                        },
                        "address": {
                            "description": "A blockchain address mentioned in the query (e.g. 0x...), if any.",
                        },
                        "case_number": {
                            "description": "A case number mentioned in the query (e.g. TRX-20240115-0042), if any.",
                        },
                        "wallet_id": {
                            "description": "An internal wallet UUID mentioned in the query, if any.",
                        },
                        "chain": {
                            "description": "The blockchain network mentioned (e.g. Ethereum, Polygon), if any.",
                        },
                    }
                )
                + ". Only return the JSON object, no additional text."
            )

            payload = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                "temperature": 0.0,  # We want deterministic classification
                "max_tokens": 256,
            }

            response = await self._require_http_client().post("/chat/completions", json=payload)
            response.raise_for_status()
            self._record_success()
            data = response.json()

            # Extract the JSON from the model's response
            content = _message_text(data)
            # Try to parse the JSON
            try:
                result: dict[str, Any] = json.loads(content)
                # Validate that we have a query_type
                if "query_type" in result and result["query_type"] in [
                    qt.value for qt in QueryType
                ]:
                    return result
                else:
                    logger.warning(
                        "openrouter_classify_invalid_response",
                        response=content,
                        query=query,
                    )
                    return None
            except json.JSONDecodeError:
                logger.warning(
                    "openrouter_classify_non_json",
                    response=content,
                    query=query,
                )
                return None

        except Exception as e:
            self._record_failure(e)
            logger.warning("openrouter_classify_failed", error=str(e), query=query)
            return None

    async def compose_answer(
        self,
        query: str,
        query_type: QueryType,
        context: dict[str, Any],
        fallback_answer: str,
    ) -> str:
        """
        Compose a natural language answer from structured context using OpenRouter.

        Returns the composed answer, or the fallback answer if unable to compose.
        """
        if not self.is_configured():
            return fallback_answer

        try:
            system_prompt = (
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

            payload = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "investigator_query": query,
                                "intent": query_type.value,
                                "context": context,
                            },
                            default=str,
                        ),
                    },
                ],
                "temperature": 0.3,  # Allow some creativity but stay grounded
                "max_tokens": 1024,
            }

            response = await self._require_http_client().post("/chat/completions", json=payload)
            response.raise_for_status()
            self._record_success()
            data = response.json()

            text = _message_text(data)
            return text or fallback_answer

        except Exception as e:
            self._record_failure(e)
            logger.warning(
                "openrouter_compose_answer_failed",
                error=str(e),
                query_type=query_type.value,
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
        Generate an investigation narrative from structured data using OpenRouter.

        Returns the generated narrative, or the fallback narrative if unable to generate.
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
                "model": self._model,
                "messages": [
                    {"role": "system", "content": narrative_system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "case": case_summary,
                                "wallets": wallets_summary,
                                "findings": findings,
                            },
                            default=str,
                        ),
                    },
                ],
                "temperature": 0.3,
                "max_tokens": 2048,
            }

            response = await self._require_http_client().post("/chat/completions", json=payload)
            response.raise_for_status()
            self._record_success()
            data = response.json()

            text = _message_text(data)
            return text or fallback_narrative

        except Exception as e:
            self._record_failure(e)
            logger.warning("openrouter_generate_narrative_failed", error=str(e))
            return fallback_narrative

    async def close(self) -> None:
        if self._http_client:
            await self._http_client.aclose()
