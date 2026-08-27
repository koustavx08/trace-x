from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
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
    value_usd: Optional[float] = None
    token_address: Optional[str] = None
    token_symbol: Optional[str] = None
    token_decimals: Optional[int] = None
    method: Optional[str] = None
    gas_used: Optional[int] = None
    gas_price: Optional[str] = None
    status: int = 1
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class WalletBalance:
    address: str
    chain: str
    eth_balance: str
    eth_balance_usd: Optional[float] = None
    tokens: List[Dict[str, Any]] = None
    last_updated: Optional[datetime] = None


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
    async def get_block(self, block_number: int) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def get_transaction(self, tx_hash: str) -> Optional[BlockchainTransaction]:
        pass

    @abstractmethod
    async def get_transactions_by_address(
        self,
        address: str,
        start_block: int = 0,
        end_block: Optional[int] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> List[BlockchainTransaction]:
        pass

    @abstractmethod
    async def get_wallet_balance(self, address: str) -> WalletBalance:
        pass

    @abstractmethod
    async def get_token_transfers(
        self,
        address: str,
        token_address: Optional[str] = None,
        start_block: int = 0,
        end_block: Optional[int] = None,
    ) -> List[BlockchainTransaction]:
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


class ProviderRegistry:
    _providers: Dict[int, BlockchainProvider] = {}
    _default_provider: Optional[BlockchainProvider] = None

    @classmethod
    def register(cls, provider: BlockchainProvider) -> None:
        cls._providers[provider.chain_id] = provider
        logger.info("provider_registered", chain_id=provider.chain_id, chain_name=provider.chain_name)

    @classmethod
    def get_provider(cls, chain_id: int) -> Optional[BlockchainProvider]:
        return cls._providers.get(chain_id)

    @classmethod
    def get_provider_by_name(cls, chain_name: str) -> Optional[BlockchainProvider]:
        for provider in cls._providers.values():
            if provider.chain_name.lower() == chain_name.lower():
                return provider
        return None

    @classmethod
    def set_default(cls, provider: BlockchainProvider) -> None:
        cls._default_provider = provider

    @classmethod
    def get_default(cls) -> Optional[BlockchainProvider]:
        return cls._default_provider

    @classmethod
    def list_chains(cls) -> List[ChainInfo]:
        return [provider.get_chain_info() for provider in cls._providers.values()]

    @classmethod
    async def close_all(cls) -> None:
        for provider in cls._providers.values():
            await provider.close()
        cls._providers.clear()
        cls._default_provider = None