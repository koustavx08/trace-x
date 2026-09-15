import structlog

from src.core.config import get_settings
from src.core.exceptions import ProviderNotConfiguredError

from .base import EntityIntelProviderRegistry, ProviderRegistry
from .bitcoin import BITCOIN_PSEUDO_CHAIN_ID, BitcoinProvider
from .chainalysis import ChainalysisProvider
from .ciphertrace import CiphertraceProvider
from .evm.alchemy import AlchemyProvider
from .evm.infura import InfuraProvider
from .tron import TRON_MAINNET_CHAIN_ID, TronProvider

logger = structlog.get_logger(__name__)


class ProviderFactory:
    _initialized = False

    @classmethod
    def initialize(cls) -> None:
        if cls._initialized:
            return

        settings = get_settings()

        # chain_id -> (Alchemy subdomain, Infura subdomain or None, name, symbol, explorer, rpc override)
        chains = [
            (
                1,
                "eth",
                "mainnet",
                "Ethereum",
                "ETH",
                "https://etherscan.io",
                settings.ETHEREUM_RPC_URL,
            ),
            (
                137,
                "polygon",
                "polygon-mainnet",
                "Polygon",
                "MATIC",
                "https://polygonscan.com",
                settings.POLYGON_RPC_URL,
            ),
            (
                42161,
                "arb",
                "arbitrum-mainnet",
                "Arbitrum",
                "ETH",
                "https://arbiscan.io",
                settings.ARBITRUM_RPC_URL,
            ),
            (
                10,
                "opt",
                "optimism-mainnet",
                "Optimism",
                "ETH",
                "https://optimistic.etherscan.io",
                settings.OPTIMISM_RPC_URL,
            ),
            (
                8453,
                "base",
                "base-mainnet",
                "Base",
                "ETH",
                "https://basescan.org",
                settings.BASE_RPC_URL,
            ),
        ]

        if settings.ALCHEMY_API_KEY:
            # WS3: AlchemyProvider now raises ProviderNotConfiguredError for a
            # blank/whitespace-only key; guard registration so that alone
            # can't crash app startup.
            try:
                for (
                    chain_id,
                    alchemy_slug,
                    _infura_slug,
                    name,
                    symbol,
                    explorer,
                    rpc_override,
                ) in chains:
                    alchemy_provider = AlchemyProvider(
                        rpc_url=rpc_override
                        or f"https://{alchemy_slug}-mainnet.g.alchemy.com/v2/{settings.ALCHEMY_API_KEY}",
                        api_key=settings.ALCHEMY_API_KEY,
                        chain_id=chain_id,
                        chain_name=name,
                        symbol=symbol,
                        explorer_url=explorer,
                    )
                    ProviderRegistry.register(alchemy_provider)
                    if chain_id == 1:
                        ProviderRegistry.set_default(alchemy_provider)
                    logger.info("alchemy_provider_registered", chain=name)
            except ProviderNotConfiguredError as e:
                logger.warning("alchemy_provider_unavailable", reason=e.message)

        if settings.INFURA_API_KEY:
            for (
                chain_id,
                _alchemy_slug,
                infura_slug,
                name,
                symbol,
                explorer,
                rpc_override,
            ) in chains:
                if ProviderRegistry.get_provider(chain_id):
                    continue
                infura_provider = InfuraProvider(
                    rpc_url=rpc_override
                    or f"https://{infura_slug}.infura.io/v3/{settings.INFURA_API_KEY}",
                    api_key=settings.INFURA_API_KEY,
                    api_secret=settings.INFURA_API_SECRET,
                    chain_id=chain_id,
                    chain_name=name,
                    symbol=symbol,
                    explorer_url=explorer,
                )
                ProviderRegistry.register(infura_provider)
                if chain_id == 1:
                    ProviderRegistry.set_default(infura_provider)
                logger.info("infura_provider_registered", chain=name)

        # BSC: neither Alchemy nor Infura support it. InfuraProvider's actual
        # requests are plain JSON-RPC POSTs to self._rpc_url with no
        # Infura-specific auth ever attached (see providers/evm/infura.py) --
        # it works with any JSON-RPC endpoint, so it's reused here directly
        # against an operator-supplied public/vendor-neutral BSC RPC URL
        # rather than writing a near-identical provider class for one chain.
        if settings.BSC_RPC_URL and not ProviderRegistry.get_provider(56):
            bsc_provider = InfuraProvider(
                rpc_url=settings.BSC_RPC_URL,
                api_key="unused",
                api_secret=None,
                chain_id=56,
                chain_name="BSC",
                symbol="BNB",
                explorer_url="https://bscscan.com",
            )
            ProviderRegistry.register(bsc_provider)
            logger.info("bsc_provider_registered")

        # --- Non-EVM chains: TRON (TRC-20 USDT) and Bitcoin (UTXO) ---
        # Neither needs a mandatory API key -- TronGrid serves anonymous traffic
        # (TRON_API_KEY only raises the rate limit) and Blockstream's Esplora is
        # fully public -- so both are registered unconditionally rather than
        # behind a key check. `chain_name` is what `get_provider_by_name` matches
        # case-insensitively, so "tron"/"bitcoin" resolve to these.
        if not ProviderRegistry.get_provider(TRON_MAINNET_CHAIN_ID):
            ProviderRegistry.register(TronProvider())
            logger.info("tron_provider_registered", chain_id=TRON_MAINNET_CHAIN_ID)

        if not ProviderRegistry.get_provider(BITCOIN_PSEUDO_CHAIN_ID):
            ProviderRegistry.register(BitcoinProvider())
            logger.info("bitcoin_provider_registered", chain_id=BITCOIN_PSEUDO_CHAIN_ID)

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
