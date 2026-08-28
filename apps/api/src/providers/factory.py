from typing import Optional, Dict
import structlog

from .base import ProviderRegistry
from .evm.alchemy import AlchemyProvider
from .evm.infura import InfuraProvider
from src.core.config import get_settings

logger = structlog.get_logger(__name__)


class ProviderFactory:
    _initialized = False

    @classmethod
    def initialize(cls) -> None:
        if cls._initialized:
            return

        settings = get_settings()

        if settings.ALCHEMY_API_KEY:
            ethalchemy = AlchemyProvider(
                rpc_url=settings.ETHEREUM_RPC_URL or f"https://eth-mainnet.g.alchemy.com/v2/{settings.ALCHEMY_API_KEY}",
                api_key=settings.ALCHEMY_API_KEY,
                chain_id=1,
                chain_name="Ethereum",
                symbol="ETH",
                explorer_url="https://etherscan.io",
            )
            ProviderRegistry.register(ethalchemy)
            ProviderRegistry.set_default(ethalchemy)
            logger.info("ethereum_alchemy_provider_registered")

            polygonalchemy = AlchemyProvider(
                rpc_url=settings.POLYGON_RPC_URL or f"https://polygon-mainnet.g.alchemy.com/v2/{settings.ALCHEMY_API_KEY}",
                api_key=settings.ALCHEMY_API_KEY,
                chain_id=137,
                chain_name="Polygon",
                symbol="MATIC",
                explorer_url="https://polygonscan.com",
            )
            ProviderRegistry.register(polygonalchemy)
            logger.info("polygon_alchemy_provider_registered")

        if settings.INFURA_API_KEY:
            ethinfura = InfuraProvider(
                rpc_url=f"https://mainnet.infura.io/v3/{settings.INFURA_API_KEY}",
                api_key=settings.INFURA_API_KEY,
                api_secret=settings.INFURA_API_SECRET,
                chain_id=1,
                chain_name="Ethereum",
                symbol="ETH",
                explorer_url="https://etherscan.io",
            )
            if not ProviderRegistry.get_provider(1):
                ProviderRegistry.register(ethinfura)
                ProviderRegistry.set_default(ethinfura)
                logger.info("ethereum_infura_provider_registered")

            polygoninfura = InfuraProvider(
                rpc_url=f"https://polygon-mainnet.infura.io/v3/{settings.INFURA_API_KEY}",
                api_key=settings.INFURA_API_KEY,
                api_secret=settings.INFURA_API_SECRET,
                chain_id=137,
                chain_name="Polygon",
                symbol="MATIC",
                explorer_url="https://polygonscan.com",
            )
            if not ProviderRegistry.get_provider(137):
                ProviderRegistry.register(polygoninfura)
                logger.info("polygon_infura_provider_registered")

        cls._initialized = True
        logger.info("provider_factory_initialized", chains=list(ProviderRegistry._providers.keys()))

    @classmethod
    def get_provider(cls, chain_id: int):
        return ProviderRegistry.get_provider(chain_id)

    @classmethod
    def get_provider_by_name(cls, chain_name: str):
        return ProviderRegistry.get_provider_by_name(chain_name)

    @classmethod
    def get_default(cls):
        return ProviderRegistry.get_default()

    @classmethod
    def list_chains(cls):
        return ProviderRegistry.list_chains()

    @classmethod
    async def close_all(cls):
        await ProviderRegistry.close_all()
        cls._initialized = False