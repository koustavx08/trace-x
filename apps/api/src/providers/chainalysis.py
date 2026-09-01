"""
Chainalysis entity-intelligence provider.

Thin client over the Chainalysis address-screening API. Implements the
narrow `EntityIntelligenceProvider` interface (see `providers/base.py`)
rather than the full `BlockchainProvider` ABC, since Chainalysis exposes
address risk/attribution data, not raw chain data.

If CHAINALYSIS_API_KEY is not set, construction raises
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


class ChainalysisProvider(EntityIntelligenceProvider):
    BASE_URL = "https://api.chainalysis.com/api/kyt/v2"

    def __init__(self, api_key: str | None = None, timeout: float = 15.0):
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.CHAINALYSIS_API_KEY

        if not self._api_key:
            raise ProviderNotConfiguredError(
                provider="chainalysis",
                message=(
                    "CHAINALYSIS_API_KEY is not set; Chainalysis entity "
                    "intelligence is unavailable."
                ),
            )

        self._http_client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Token": self._api_key, "Accept": "application/json"},
        )

    @property
    def provider_name(self) -> str:
        return "chainalysis"

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    async def get_address_risk(self, address: str, chain: str) -> EntityIntelligenceResult:
        try:
            response = await self._http_client.get(f"{self.BASE_URL}/users/{address}")
            response.raise_for_status()
            data = response.json()

            return EntityIntelligenceResult(
                address=address,
                chain=chain,
                entity_name=data.get("category") or data.get("name"),
                entity_category=data.get("category"),
                risk_score=data.get("riskScore"),
                is_sanctioned=data.get("category") == "sanctions",
                confidence=data.get("confidence"),
                tags=data.get("tags", []) or [],
                source="chainalysis",
                raw=data,
            )
        except httpx.HTTPStatusError as e:
            logger.warning(
                "chainalysis_lookup_failed",
                address=address,
                status=e.response.status_code if e.response is not None else None,
            )
            return EntityIntelligenceResult(
                address=address, chain=chain, source="chainalysis", raw={"error": str(e)}
            )
        except Exception as e:
            logger.warning("chainalysis_lookup_error", address=address, error=str(e))
            return EntityIntelligenceResult(
                address=address, chain=chain, source="chainalysis", raw={"error": str(e)}
            )

    async def health_check(self) -> bool:
        try:
            response = await self._http_client.get(f"{self.BASE_URL}/users/health")
            return response.status_code < 500
        except Exception:
            return False

    async def close(self) -> None:
        await self._http_client.aclose()
