"""
CipherTrace entity-intelligence provider.

Thin client over the CipherTrace (Mastercard) address-attribution API.
Implements the narrow `EntityIntelligenceProvider` interface (see
`providers/base.py`) rather than the full `BlockchainProvider` ABC, since
CipherTrace exposes address risk/attribution data, not raw chain data.

If CIPHERTRACE_API_KEY is not set, construction raises
`ProviderNotConfiguredError` so the factory can register this provider as
unavailable instead of silently returning empty/garbage intelligence data
or crashing app startup.
"""

import httpx
import structlog

from src.core.config import get_settings
from src.core.exceptions import ProviderNotConfiguredError

from .base import EntityIntelligenceProvider, EntityIntelligenceResult

logger = structlog.get_logger(__name__)


class CiphertraceProvider(EntityIntelligenceProvider):
    BASE_URL = "https://api.ciphertrace.com/v1"

    def __init__(self, api_key: str | None = None, timeout: float = 15.0):
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.CIPHERTRACE_API_KEY

        if not self._api_key:
            raise ProviderNotConfiguredError(
                provider="ciphertrace",
                message=(
                    "CIPHERTRACE_API_KEY is not set; CipherTrace entity "
                    "intelligence is unavailable."
                ),
            )

        self._http_client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {self._api_key}", "Accept": "application/json"},
        )

    @property
    def provider_name(self) -> str:
        return "ciphertrace"

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def get_address_risk(self, address: str, chain: str) -> EntityIntelligenceResult:
        try:
            response = await self._http_client.get(
                f"{self.BASE_URL}/attribution/address/{address}",
                params={"chain": chain},
            )
            response.raise_for_status()
            data = response.json()

            return EntityIntelligenceResult(
                address=address,
                chain=chain,
                entity_name=data.get("entity") or data.get("owner"),
                entity_category=data.get("entityType"),
                risk_score=data.get("riskScore"),
                is_sanctioned=bool(data.get("sanctioned")),
                confidence=data.get("confidenceLevel"),
                tags=data.get("labels", []) or [],
                source="ciphertrace",
                raw=data,
            )
        except httpx.HTTPStatusError as e:
            logger.warning(
                "ciphertrace_lookup_failed",
                address=address,
                status=e.response.status_code if e.response is not None else None,
            )
            return EntityIntelligenceResult(
                address=address, chain=chain, source="ciphertrace", raw={"error": str(e)}
            )
        except Exception as e:
            logger.warning("ciphertrace_lookup_error", address=address, error=str(e))
            return EntityIntelligenceResult(
                address=address, chain=chain, source="ciphertrace", raw={"error": str(e)}
            )

    async def health_check(self) -> bool:
        try:
            response = await self._http_client.get(f"{self.BASE_URL}/health")
            return response.status_code < 500
        except Exception:
            return False

    async def close(self) -> None:
        await self._http_client.aclose()
