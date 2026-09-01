import structlog

from src.core.config import get_settings
from src.core.exceptions import ProviderNotConfiguredError

from .base import EntityIntelProviderRegistry, ProviderRegistry
from .chainalysis import ChainalysisProvider
from .ciphertrace import CiphertraceProvider
from .evm.alchemy import AlchemyProvider
from .evm.infura import InfuraProvider

logger = structlog.get_logger(__name__)


class ProviderFactory:
    _initialized = False

    @classmethod
    def initialize(cls) -> None:
        if cls._initialized:
            return

        settings = get_settings()

        if settings.ALCHEMY_API_KEY:
            # WS3: AlchemyProvider now raises ProviderNotConfiguredError for a
            # blank/whitespace-only key; guard registration so that alone
            # can't crash app startup.
            try:
                ethalchemy = AlchemyProvider(
                    rpc_url=settings.ETHEREUM_RPC_URL
                    or f"https://eth-mainnet.g.alchemy.com/v2/{settings.ALCHEMY_API_KEY}",
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
                    rpc_url=settings.POLYGON_RPC_URL
                    or f"https://polygon-mainnet.g.alchemy.com/v2/{settings.ALCHEMY_API_KEY}",
                    api_key=settings.ALCHEMY_API_KEY,
                    chain_id=137,
                    chain_name="Polygon",
                    symbol="MATIC",
                    explorer_url="https://polygonscan.com",
                )
                ProviderRegistry.register(polygonalchemy)
                logger.info("polygon_alchemy_provider_registered")
            except ProviderNotConfiguredError as e:
                logger.warning("alchemy_provider_unavailable", reason=e.message)

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

        # --- WS3: entity-intelligence providers (Chainalysis / CipherTrace) ---
        # Each provider raises ProviderNotConfiguredError at construction time
        # when its API key is absent. Registration must never crash app
        # startup, so each is attempted independently and simply skipped
        # (logged) when unavailable.
        try:
            chainalysis = ChainalysisProvider()
            EntityIntelProviderRegistry.register(chainalysis)
            logger.info("chainalysis_provider_registered")
        except ProviderNotConfiguredError as e:
            logger.info("chainalysis_provider_unavailable", reason=e.message)

        try:
            ciphertrace = CiphertraceProvider()
            EntityIntelProviderRegistry.register(ciphertrace)
            logger.info("ciphertrace_provider_registered")
        except ProviderNotConfiguredError as e:
            logger.info("ciphertrace_provider_unavailable", reason=e.message)
        # --- end WS3 block ---

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
    async def list_chains(cls):
        return await ProviderRegistry.list_chains()

    # --- WS3: entity-intelligence provider accessors (appended) ---
    @classmethod
    def get_entity_intel_provider(cls, name: str):
        return EntityIntelProviderRegistry.get(name)

    @classmethod
    def list_entity_intel_providers(cls):
        return EntityIntelProviderRegistry.list_available()

    # --- end WS3 block ---

    @classmethod
    async def close_all(cls):
        await ProviderRegistry.close_all()
        await EntityIntelProviderRegistry.close_all()
        cls._initialized = False
