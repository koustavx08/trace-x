from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BlockchainTransaction:
    tx_hash: str
    block_number: int
    timestamp: datetime
    from_address: str
    to_address: str
    value: str
    value_usd: float | None = None
    token_address: str | None = None
    token_symbol: str | None = None
    token_decimals: int | None = None
    method: str | None = None
    gas_used: int | None = None
    gas_price: str | None = None
    status: int = 1
    metadata: dict[str, Any] | None = None


@dataclass
class WalletBalance:
    address: str
    chain: str
    eth_balance: str
    eth_balance_usd: float | None = None
    tokens: list[dict[str, Any]] = field(default_factory=list)
    last_updated: datetime | None = None


@dataclass
class ChainInfo:
    chain_id: int
    name: str
    symbol: str
    rpc_url: str
    explorer_url: str
    is_testnet: bool = False


class BlockchainProvider(ABC):
    @property
    @abstractmethod
    def chain_id(self) -> int:
        pass

    @property
    @abstractmethod
    def chain_name(self) -> str:
        pass

    @abstractmethod
    async def get_latest_block(self) -> int:
        pass

    @abstractmethod
    async def get_block(self, block_number: int) -> dict[str, Any] | None:
        pass

    @abstractmethod
    async def get_transaction(self, tx_hash: str) -> BlockchainTransaction | None:
        pass

    @abstractmethod
    async def get_transactions_by_address(
        self,
        address: str,
        start_block: int = 0,
        end_block: int | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> list[BlockchainTransaction]:
        pass

    @abstractmethod
    async def get_wallet_balance(self, address: str) -> WalletBalance:
        pass

    @abstractmethod
    async def get_token_transfers(
        self,
        address: str,
        token_address: str | None = None,
        start_block: int = 0,
        end_block: int | None = None,
    ) -> list[BlockchainTransaction]:
        pass

    @abstractmethod
    async def validate_address(self, address: str) -> bool:
        pass

    @abstractmethod
    async def get_chain_info(self) -> ChainInfo:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass


# --- WS3: entity-intelligence provider interface (appended) ---
# Chainalysis/CipherTrace-style services expose address risk/attribution
# intelligence, not raw chain data (blocks/transactions/balances), so they
# don't fit the BlockchainProvider ABC above. This is a narrower, parallel
# interface for that category of provider.
@dataclass
class EntityIntelligenceResult:
    address: str
    chain: str
    entity_name: str | None = None
    entity_category: str | None = None
    risk_score: float | None = None
    is_sanctioned: bool = False
    confidence: str | None = None
    tags: list[str] | None = None
    source: str = "unknown"
    raw: dict[str, Any] | None = None


class EntityIntelligenceProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    async def get_address_risk(self, address: str, chain: str) -> EntityIntelligenceResult:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass


class EntityIntelProviderRegistry:
    _providers: dict[str, EntityIntelligenceProvider] = {}

    @classmethod
    def register(cls, provider: EntityIntelligenceProvider) -> None:
        cls._providers[provider.provider_name] = provider
        logger.info("entity_intel_provider_registered", provider=provider.provider_name)

    @classmethod
    def get(cls, name: str) -> EntityIntelligenceProvider | None:
        return cls._providers.get(name)

    @classmethod
    def list_available(cls) -> list[str]:
        return list(cls._providers.keys())

    @classmethod
    async def close_all(cls) -> None:
        for provider in cls._providers.values():
            await provider.close()
        cls._providers.clear()


# --- end WS3 block ---


class ProviderRegistry:
    _providers: dict[int, BlockchainProvider] = {}
    _default_provider: BlockchainProvider | None = None

    @classmethod
    def register(cls, provider: BlockchainProvider) -> None:
        cls._providers[provider.chain_id] = provider
        logger.info(
            "provider_registered", chain_id=provider.chain_id, chain_name=provider.chain_name
        )

    @classmethod
    def get_provider(cls, chain_id: int) -> BlockchainProvider | None:
        return cls._providers.get(chain_id)

    @classmethod
    def get_provider_by_name(cls, chain_name: str) -> BlockchainProvider | None:
        for provider in cls._providers.values():
            if provider.chain_name.lower() == chain_name.lower():
                return provider
        return None

    @classmethod
    def set_default(cls, provider: BlockchainProvider) -> None:
        cls._default_provider = provider

    @classmethod
    def get_default(cls) -> BlockchainProvider | None:
        return cls._default_provider

    @classmethod
    async def list_chains(cls) -> list[ChainInfo]:
        return [await provider.get_chain_info() for provider in cls._providers.values()]

    @classmethod
    async def close_all(cls) -> None:
        for provider in cls._providers.values():
            await provider.close()
        cls._providers.clear()
        cls._default_provider = None
