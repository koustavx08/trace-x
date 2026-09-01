"""
Tests for src/providers/base.py, src/providers/evm/base.py,
src/providers/evm/infura.py, src/providers/evm/alchemy.py and
src/providers/factory.py.

All web3/httpx calls are mocked -- these tests never touch a real RPC
endpoint or the network, so they run deterministically with no
infrastructure dependency (no Postgres/Neo4j/Docker needed).

WS3 owns `providers/chainalysis.py`, `providers/ciphertrace.py`, a new
`ProviderNotConfiguredError` in `core/exceptions.py`, and fixing
`InfuraProvider.get_transactions_by_address`/`get_token_transfers` (which
currently discard their RPC result / are unconditional `[]`). Those tests
are written defensively (skip if not present yet) so they document the gap
without failing the suite.
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.providers.base import (
    BlockchainProvider,
    BlockchainTransaction,
    ChainInfo,
    ProviderRegistry,
    WalletBalance,
)
from src.providers.evm.alchemy import AlchemyProvider
from src.providers.evm.infura import InfuraProvider


ADDRESS = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"


def _make_alchemy_provider() -> AlchemyProvider:
    return AlchemyProvider(
        rpc_url="https://eth-mainnet.g.alchemy.com/v2/test-key",
        api_key="test-key",
        chain_id=1,
        chain_name="Ethereum",
        symbol="ETH",
        explorer_url="https://etherscan.io",
    )


def _make_infura_provider() -> InfuraProvider:
    return InfuraProvider(
        rpc_url="https://mainnet.infura.io/v3/test-key",
        api_key="test-key",
        api_secret=None,
        chain_id=1,
        chain_name="Ethereum",
        symbol="ETH",
        explorer_url="https://etherscan.io",
    )


# ---------------------------------------------------------------------------
# ProviderRegistry (pure in-memory logic)
# ---------------------------------------------------------------------------

class TestProviderRegistry:
    def setup_method(self):
        ProviderRegistry._providers = {}
        ProviderRegistry._default_provider = None

    def teardown_method(self):
        ProviderRegistry._providers = {}
        ProviderRegistry._default_provider = None

    def test_register_and_get_provider(self):
        provider = _make_alchemy_provider()
        ProviderRegistry.register(provider)
        assert ProviderRegistry.get_provider(1) is provider

    def test_get_provider_by_name_case_insensitive(self):
        provider = _make_alchemy_provider()
        ProviderRegistry.register(provider)
        assert ProviderRegistry.get_provider_by_name("ethereum") is provider
        assert ProviderRegistry.get_provider_by_name("ETHEREUM") is provider

    def test_get_provider_by_name_unknown_returns_none(self):
        assert ProviderRegistry.get_provider_by_name("nonexistent-chain") is None

    def test_get_provider_unknown_chain_id_returns_none(self):
        assert ProviderRegistry.get_provider(999999) is None

    def test_set_and_get_default(self):
        provider = _make_alchemy_provider()
        ProviderRegistry.set_default(provider)
        assert ProviderRegistry.get_default() is provider

    async def test_close_all_clears_registry(self):
        provider = _make_alchemy_provider()
        provider.close = AsyncMock()
        ProviderRegistry.register(provider)
        ProviderRegistry.set_default(provider)

        await ProviderRegistry.close_all()

        provider.close.assert_awaited_once()
        assert ProviderRegistry.get_provider(1) is None
        assert ProviderRegistry.get_default() is None


# ---------------------------------------------------------------------------
# EVMProvider base behavior (via the Alchemy subclass) with mocked Web3
# ---------------------------------------------------------------------------

class TestEVMProviderBase:
    def test_chain_id_and_name_properties(self):
        provider = _make_alchemy_provider()
        assert provider.chain_id == 1
        assert provider.chain_name == "Ethereum"

    async def test_get_chain_info(self):
        provider = _make_alchemy_provider()
        info = await provider.get_chain_info()
        assert isinstance(info, ChainInfo)
        assert info.chain_id == 1
        assert info.symbol == "ETH"

    async def test_validate_address_valid(self):
        provider = _make_alchemy_provider()
        assert await provider.validate_address(ADDRESS) is True

    async def test_validate_address_invalid(self):
        provider = _make_alchemy_provider()
        assert await provider.validate_address("not-an-address") is False

    async def test_get_latest_block(self, monkeypatch):
        provider = _make_alchemy_provider()
        monkeypatch.setattr(
            type(provider._w3.eth), "block_number", property(lambda self: 12345678), raising=False
        )
        assert await provider.get_latest_block() == 12345678

    async def test_health_check_true_when_block_positive(self, monkeypatch):
        provider = _make_alchemy_provider()
        provider.get_latest_block = AsyncMock(return_value=100)
        assert await provider.health_check() is True

    async def test_health_check_false_on_exception(self):
        provider = _make_alchemy_provider()
        provider.get_latest_block = AsyncMock(side_effect=RuntimeError("rpc down"))
        assert await provider.health_check() is False

    async def test_get_wallet_balance_failure_returns_zero_balance(self, monkeypatch):
        provider = _make_alchemy_provider()
        # AlchemyProvider overrides get_wallet_balance; force the httpx call
        # to fail so it falls back to the base implementation, which itself
        # should gracefully degrade to a "0" balance rather than raising.
        provider._http_client.post = AsyncMock(side_effect=RuntimeError("network down"))
        balance = await provider.get_wallet_balance(ADDRESS)
        assert isinstance(balance, WalletBalance)
        assert balance.eth_balance == "0"

    async def test_close_closes_http_client(self):
        provider = _make_alchemy_provider()
        provider._http_client.aclose = AsyncMock()
        await provider.close()
        provider._http_client.aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# AlchemyProvider.get_transactions_by_address / get_token_transfers (mocked httpx)
# ---------------------------------------------------------------------------

def _mock_response(json_data):
    response = MagicMock()
    response.json.return_value = json_data
    response.raise_for_status = MagicMock()
    return response


class TestAlchemyProviderTransactions:
    async def test_get_transactions_by_address_parses_transfers(self):
        provider = _make_alchemy_provider()
        transfers_payload = {
            "result": {
                "transfers": [
                    {
                        "hash": "0xabc",
                        "blockNum": "0x10",
                        "from": ADDRESS,
                        "to": "0x0000000000000000000000000000000000dead",
                        "value": 1.5,
                        "category": "external",
                        "metadata": {"blockTimestamp": "2024-01-15T10:00:00Z"},
                    }
                ]
            }
        }
        provider._http_client.post = AsyncMock(return_value=_mock_response(transfers_payload))

        transactions = await provider.get_transactions_by_address(ADDRESS)

        assert len(transactions) == 1
        tx = transactions[0]
        assert isinstance(tx, BlockchainTransaction)
        assert tx.tx_hash == "0xabc"
        assert tx.block_number == 16
        assert tx.from_address == ADDRESS

    async def test_get_transactions_by_address_returns_empty_on_error(self):
        provider = _make_alchemy_provider()
        provider._http_client.post = AsyncMock(side_effect=RuntimeError("timeout"))
        transactions = await provider.get_transactions_by_address(ADDRESS)
        assert transactions == []

    async def test_get_token_transfers_parses_erc20(self):
        provider = _make_alchemy_provider()
        transfers_payload = {
            "result": {
                "transfers": [
                    {
                        "hash": "0xdef",
                        "blockNum": "0x20",
                        "from": ADDRESS,
                        "to": "0x0000000000000000000000000000000000beef",
                        "value": 100,
                        "category": "erc20",
                        "erc20Metadata": {"symbol": "USDC", "decimals": 6},
                        "rawContract": {"address": "0xcontract"},
                    }
                ]
            }
        }
        provider._http_client.post = AsyncMock(return_value=_mock_response(transfers_payload))

        transactions = await provider.get_token_transfers(ADDRESS)

        assert len(transactions) == 1
        assert transactions[0].token_symbol == "USDC"

    async def test_get_token_transfers_returns_empty_on_error(self):
        provider = _make_alchemy_provider()
        provider._http_client.post = AsyncMock(side_effect=RuntimeError("timeout"))
        assert await provider.get_token_transfers(ADDRESS) == []


# ---------------------------------------------------------------------------
# InfuraProvider -- documents current (incomplete) behavior for WS3 fixup
# ---------------------------------------------------------------------------

class TestInfuraProviderCurrentBehavior:
    async def test_get_transactions_by_address_currently_always_empty(self):
        """KNOWN GAP: InfuraProvider.get_transactions_by_address makes an
        eth_getTransactionCount RPC call, discards the result, and
        unconditionally `return []`. WS3 owns implementing this for real.
        This test pins today's actual (incomplete) behavior; once WS3
        implements it, this test should be replaced with one asserting
        real parsed transactions."""
        provider = _make_infura_provider()
        provider._http_client.post = AsyncMock(
            return_value=_mock_response({"jsonrpc": "2.0", "id": 1, "result": "0x5"})
        )
        transactions = await provider.get_transactions_by_address(ADDRESS)
        assert transactions == []

    async def test_get_token_transfers_currently_always_empty(self):
        """KNOWN GAP: unconditionally returns [] with no RPC call at all."""
        provider = _make_infura_provider()
        assert await provider.get_token_transfers(ADDRESS) == []

    async def test_get_transactions_by_address_swallows_errors(self):
        provider = _make_infura_provider()
        provider._http_client.post = AsyncMock(side_effect=RuntimeError("rpc error"))
        # Should not raise -- current implementation catches and returns [].
        assert await provider.get_transactions_by_address(ADDRESS) == []


# ---------------------------------------------------------------------------
# ProviderNotConfiguredError / new WS3 providers -- not landed in this worktree
# ---------------------------------------------------------------------------

class TestWS3ProvidersNotYetLanded:
    def test_provider_not_configured_error_not_yet_added(self):
        import src.core.exceptions as exceptions_module

        if not hasattr(exceptions_module, "ProviderNotConfiguredError"):
            pytest.skip("ProviderNotConfiguredError not added yet (WS3)")
        assert issubclass(exceptions_module.ProviderNotConfiguredError, Exception)

    def test_chainalysis_provider_module_not_yet_added(self):
        pytest.importorskip(
            "src.providers.chainalysis", reason="providers/chainalysis.py not added yet (WS3)"
        )

    def test_ciphertrace_provider_module_not_yet_added(self):
        pytest.importorskip(
            "src.providers.ciphertrace", reason="providers/ciphertrace.py not added yet (WS3)"
        )
