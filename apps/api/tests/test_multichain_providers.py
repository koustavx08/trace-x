"""
Tests for src/providers/tron.py and src/providers/bitcoin.py -- the non-EVM
(TRON / Bitcoin) chain providers, plus their registration in
src/providers/factory.py.

NO NETWORK ACCESS. `respx` is not installed in this environment, so TronGrid
and Blockstream are served by canned JSON fixtures through
`httpx.MockTransport`, which both providers accept via their `transport=`
constructor argument. Every test is therefore deterministic and needs no
infrastructure (no Postgres/Neo4j/Docker, no API keys).

Retry backoff is set to 0 in the helpers so the retry-path tests do not sleep.
"""

import inspect

import httpx
import pytest

from src.core.exceptions import ExternalServiceError
from src.providers.base import (
    BlockchainProvider,
    BlockchainTransaction,
    ChainInfo,
    ProviderRegistry,
    WalletBalance,
)
from src.providers.bitcoin import (
    BITCOIN_PSEUDO_CHAIN_ID,
    COINBASE_SENDER,
    BitcoinProvider,
)
from src.providers.factory import ProviderFactory
from src.providers.tron import (
    TRON_MAINNET_CHAIN_ID,
    USDT_TRC20_CONTRACT,
    TronProvider,
    normalize_tron_address,
)

# Real, checksum-valid mainnet addresses (Binance-style hot wallet + the USDT
# TRC-20 contract). Mixed case is load-bearing: TRON base58 is case-sensitive.
TRON_ADDRESS = "TMuA6YqfCeX8EhbfYEg5y7S4DqzSJireY9"
TRON_COUNTERPARTY = "TLa2f6VPqDgRE67v1736s7bJ8Ray5wYjU7"
TRON_ADDRESS_HEX = "4182dd6b9966724ae2fdc79b416c7588da67ff1b35"
TRON_COUNTERPARTY_HEX41 = "4174472e7d35395a6b5add427eecb7f4b62ad2b071"

# Bitcoin genesis address (P2PKH) and a BIP-173 bech32 example.
BTC_ADDRESS = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
BTC_ADDRESS_2 = "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy"
BTC_BECH32 = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"


# ---------------------------------------------------------------------------
# httpx.MockTransport plumbing (respx is not available here)
# ---------------------------------------------------------------------------


def _json_route(payload, status: int = 200):
    def route(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    return route


def _text_route(body: str, status: int = 200):
    def route(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body)

    return route


def _make_transport(routes: dict) -> httpx.MockTransport:
    """Serve canned responses keyed by URL path; anything unrouted 404s."""

    def handler(request: httpx.Request) -> httpx.Response:
        route = routes.get(request.url.path)
        if route is None:
            return httpx.Response(404, json={"error": "unrouted", "path": request.url.path})
        return route(request)

    return httpx.MockTransport(handler)


def _tron(routes: dict, **kwargs) -> TronProvider:
    return TronProvider(
        api_key="test-key",
        max_retries=kwargs.pop("max_retries", 1),
        retry_backoff=0.0,
        transport=_make_transport(routes),
        **kwargs,
    )


def _bitcoin(routes: dict, **kwargs) -> BitcoinProvider:
    return BitcoinProvider(
        max_retries=kwargs.pop("max_retries", 1),
        retry_backoff=0.0,
        transport=_make_transport(routes),
        **kwargs,
    )


def _trc20_payload(value: str, decimals: int = 6, symbol: str = "USDT") -> dict:
    return {
        "success": True,
        "data": [
            {
                "transaction_id": "9f4c1b2a0000000000000000000000000000000000000000000000000000abcd",
                "block_timestamp": 1700000000000,
                "from": TRON_ADDRESS,
                "to": TRON_COUNTERPARTY,
                "type": "Transfer",
                "value": value,
                "token_info": {
                    "symbol": symbol,
                    "address": USDT_TRC20_CONTRACT,
                    "decimals": decimals,
                    "name": "Tether USD",
                },
            }
        ],
        "meta": {"page_size": 1},
    }


def _native_trx_payload(amount: int = 1_500_000) -> dict:
    return {
        "success": True,
        "data": [
            {
                "txID": "1111111111111111111111111111111111111111111111111111111111111111",
                "blockNumber": 55_000_000,
                "block_timestamp": 1700000000000,
                "ret": [{"contractRet": "SUCCESS"}],
                "raw_data": {
                    "contract": [
                        {
                            "type": "TransferContract",
                            "parameter": {
                                "value": {
                                    "owner_address": TRON_ADDRESS,
                                    "to_address": TRON_COUNTERPARTY,
                                    "amount": amount,
                                }
                            },
                        }
                    ]
                },
            }
        ],
        "meta": {"page_size": 1},
    }


def _trc20_calldata(recipient_hex_no_prefix: str, amount: int) -> str:
    """Encode `transfer(address,uint256)` calldata the way TRON does."""
    return "a9059cbb" + recipient_hex_no_prefix.rjust(64, "0") + f"{amount:064x}"


# ---------------------------------------------------------------------------
# TronProvider -- TRC-20 (the 70%-of-Indian-cybercrime case)
# ---------------------------------------------------------------------------


class TestTronTrc20Transfers:
    async def test_trc20_usdt_transfer_uses_six_decimals(self):
        """USDT-TRC20 has 6 decimals; 1_234_567_891 base units is 1234.567891
        USDT, NOT 1.234567891e-9 (which an 18-decimal assumption would give)."""
        provider = _tron(
            {
                f"/v1/accounts/{TRON_ADDRESS}/transactions/trc20": _json_route(
                    _trc20_payload("1234567891")
                )
            }
        )

        transfers = await provider.get_token_transfers(TRON_ADDRESS)

        assert len(transfers) == 1
        transfer = transfers[0]
        assert isinstance(transfer, BlockchainTransaction)
        assert transfer.value == "1234.567891"
        assert transfer.token_decimals == 6
        assert transfer.token_symbol == "USDT"
        assert transfer.token_address == USDT_TRC20_CONTRACT
        assert transfer.from_address == TRON_ADDRESS
        assert transfer.to_address == TRON_COUNTERPARTY
        assert transfer.metadata["raw_value"] == "1234567891"
        assert transfer.metadata["transfer_type"] == "trc20"

    async def test_trc20_transfer_never_assumes_18_decimals(self):
        provider = _tron(
            {
                f"/v1/accounts/{TRON_ADDRESS}/transactions/trc20": _json_route(
                    _trc20_payload("5000000")
                )
            }
        )

        transfers = await provider.get_token_transfers(TRON_ADDRESS)

        # 5_000_000 / 10**6 == 5 USDT. An 18-decimal conversion would have
        # produced 0.000000000005.
        assert transfers[0].value == "5"

    async def test_trc20_addresses_keep_their_case(self):
        provider = _tron(
            {
                f"/v1/accounts/{TRON_ADDRESS}/transactions/trc20": _json_route(
                    _trc20_payload("1000000")
                )
            }
        )

        transfer = (await provider.get_token_transfers(TRON_ADDRESS))[0]

        assert transfer.from_address != transfer.from_address.lower()
        assert transfer.to_address == TRON_COUNTERPARTY


class TestTronNativeTransactions:
    async def test_native_trx_transfer_parsed(self):
        provider = _tron(
            {f"/v1/accounts/{TRON_ADDRESS}/transactions": _json_route(_native_trx_payload())}
        )

        transactions = await provider.get_transactions_by_address(TRON_ADDRESS)

        assert len(transactions) == 1
        tx = transactions[0]
        # 1_500_000 SUN == 1.5 TRX (TRX also has 6 decimals).
        assert tx.value == "1.5"
        assert tx.token_symbol == "TRX"
        assert tx.token_decimals == 6
        assert tx.from_address == TRON_ADDRESS
        assert tx.to_address == TRON_COUNTERPARTY
        assert tx.block_number == 55_000_000
        assert tx.status == 1
        assert tx.timestamp.year == 2023

    async def test_native_transaction_hex_addresses_normalized_to_base58(self):
        payload = _native_trx_payload()
        value_map = payload["data"][0]["raw_data"]["contract"][0]["parameter"]["value"]
        value_map["owner_address"] = TRON_ADDRESS_HEX
        value_map["to_address"] = TRON_COUNTERPARTY_HEX41

        provider = _tron({f"/v1/accounts/{TRON_ADDRESS}/transactions": _json_route(payload)})

        tx = (await provider.get_transactions_by_address(TRON_ADDRESS))[0]

        assert tx.from_address == TRON_ADDRESS
        assert tx.to_address == TRON_COUNTERPARTY

    async def test_trigger_smart_contract_trc20_calldata_decoded(self):
        """A TRC-20 transfer appears on the native endpoint as a
        TriggerSmartContract whose calldata is the `transfer(address,uint256)`
        call behind the `Transfer(address,address,uint256)` log."""
        payload = {
            "success": True,
            "data": [
                {
                    "txID": "2222222222222222222222222222222222222222222222222222222222222222",
                    "blockNumber": 55_000_100,
                    "block_timestamp": 1700000000000,
                    "ret": [{"contractRet": "SUCCESS"}],
                    "raw_data": {
                        "contract": [
                            {
                                "type": "TriggerSmartContract",
                                "parameter": {
                                    "value": {
                                        "owner_address": TRON_ADDRESS,
                                        "contract_address": USDT_TRC20_CONTRACT,
                                        "data": _trc20_calldata(
                                            TRON_COUNTERPARTY_HEX41[2:], 250_000_000
                                        ),
                                    }
                                },
                            }
                        ]
                    },
                }
            ],
            "meta": {},
        }
        provider = _tron({f"/v1/accounts/{TRON_ADDRESS}/transactions": _json_route(payload)})

        tx = (await provider.get_transactions_by_address(TRON_ADDRESS))[0]

        assert tx.to_address == TRON_COUNTERPARTY
        assert tx.token_address == USDT_TRC20_CONTRACT
        # 250_000_000 base units / 10**6 == 250 USDT.
        assert tx.value == "250"
        assert tx.token_decimals == 6
        assert tx.method == "transfer"

    async def test_block_range_filter_applied_client_side(self):
        provider = _tron(
            {f"/v1/accounts/{TRON_ADDRESS}/transactions": _json_route(_native_trx_payload())}
        )

        assert (
            await provider.get_transactions_by_address(TRON_ADDRESS, start_block=60_000_000) == []
        )
        assert (
            await provider.get_transactions_by_address(TRON_ADDRESS, end_block=54_000_000)
        ) == []


class TestTronAddressValidation:
    async def test_accepts_valid_t_address(self):
        provider = _tron({})
        assert await provider.validate_address(TRON_ADDRESS) is True
        assert await provider.validate_address(USDT_TRC20_CONTRACT) is True

    async def test_rejects_garbage_and_evm_addresses(self):
        provider = _tron({})
        assert await provider.validate_address("not-an-address") is False
        assert await provider.validate_address("") is False
        assert (
            await provider.validate_address("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb1") is False
        )
        # Right shape, wrong checksum.
        assert await provider.validate_address("T" + "M" * 33) is False

    async def test_never_lowercases_tron_addresses(self):
        """Base58 is case-sensitive: a lowercased TRON address is a DIFFERENT,
        invalid address and must not be silently accepted or normalized."""
        provider = _tron({})
        assert await provider.validate_address(TRON_ADDRESS.lower()) is False
        assert normalize_tron_address(TRON_ADDRESS) == TRON_ADDRESS
        assert normalize_tron_address(TRON_ADDRESS_HEX) == TRON_ADDRESS


class TestTronErrorHandling:
    async def test_non_200_surfaces_provider_error(self):
        provider = _tron(
            {
                f"/v1/accounts/{TRON_ADDRESS}/transactions/trc20": _json_route(
                    {"error": "bad request"}, status=400
                )
            }
        )

        with pytest.raises(ExternalServiceError) as excinfo:
            await provider.get_token_transfers(TRON_ADDRESS)

        assert "400" in excinfo.value.message
        assert excinfo.value.status_code == 502

    async def test_trongrid_success_false_surfaces_provider_error(self):
        provider = _tron(
            {
                f"/v1/accounts/{TRON_ADDRESS}/transactions": _json_route(
                    {"success": False, "error": "invalid parameter", "data": []}
                )
            }
        )

        with pytest.raises(ExternalServiceError):
            await provider.get_transactions_by_address(TRON_ADDRESS)

    async def test_server_error_is_retried_then_raises(self):
        calls: list[int] = []

        def flaky(_request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(503, json={"error": "upstream unavailable"})

        provider = _tron({f"/v1/accounts/{TRON_ADDRESS}/transactions/trc20": flaky}, max_retries=3)

        with pytest.raises(ExternalServiceError):
            await provider.get_token_transfers(TRON_ADDRESS)

        assert len(calls) == 3  # retried with backoff before giving up

    async def test_invalid_address_rejected_before_any_http_call(self):
        provider = _tron({})
        with pytest.raises(ExternalServiceError):
            await provider.get_transactions_by_address("not-an-address")


class TestTronAccountData:
    async def test_get_wallet_balance_converts_trx_and_trc20(self):
        provider = _tron(
            {
                f"/v1/accounts/{TRON_ADDRESS}": _json_route(
                    {
                        "success": True,
                        "data": [
                            {
                                "address": TRON_ADDRESS,
                                "balance": 12_345_678,
                                "trc20": [{USDT_TRC20_CONTRACT: "2500000"}],
                            }
                        ],
                    }
                )
            }
        )

        balance = await provider.get_wallet_balance(TRON_ADDRESS)

        assert isinstance(balance, WalletBalance)
        assert balance.chain == "Tron"
        assert balance.eth_balance == "12.345678"  # native-balance field carries TRX
        assert balance.tokens[0]["symbol"] == "USDT"
        assert balance.tokens[0]["balance"] == "2.5"
        assert balance.tokens[0]["raw_balance"] == "2500000"

    async def test_latest_block_and_health_check(self):
        provider = _tron(
            {
                "/wallet/getnowblock": _json_route(
                    {"block_header": {"raw_data": {"number": 66_000_000}}}
                )
            }
        )

        assert await provider.get_latest_block() == 66_000_000
        assert await provider.health_check() is True

    async def test_health_check_false_when_trongrid_unreachable(self):
        def dead(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("trongrid unreachable")

        provider = _tron({"/wallet/getnowblock": dead})
        assert await provider.health_check() is False

    async def test_get_chain_info_and_identity(self):
        provider = _tron({})
        info = await provider.get_chain_info()

        assert isinstance(info, ChainInfo)
        assert info.chain_id == TRON_MAINNET_CHAIN_ID == 728126428
        assert info.symbol == "TRX"
        assert provider.chain_name == "Tron"


# ---------------------------------------------------------------------------
# BitcoinProvider -- UTXO -> account mapping
# ---------------------------------------------------------------------------


def _btc_tx(vin: list, vout: list, *, txid: str = "aa" * 32, fee: int = 0) -> dict:
    return {
        "txid": txid,
        "fee": fee,
        "vin": vin,
        "vout": vout,
        "status": {"confirmed": True, "block_height": 800_000, "block_time": 1690000000},
    }


def _vin(address: str | None, value: int, coinbase: bool = False) -> dict:
    if coinbase:
        return {"is_coinbase": True, "prevout": None}
    return {"is_coinbase": False, "prevout": {"scriptpubkey_address": address, "value": value}}


def _vout(address: str | None, value: int) -> dict:
    out: dict = {"value": value}
    if address:
        out["scriptpubkey_address"] = address
    return out


class TestBitcoinUtxoMapping:
    async def test_single_input_single_output_leg_with_sat_to_btc(self):
        tx = _btc_tx([_vin(BTC_ADDRESS, 100_000)], [_vout(BTC_ADDRESS_2, 90_000)], fee=10_000)
        provider = _bitcoin({f"/address/{BTC_ADDRESS}/txs": _json_route([tx])})

        legs = await provider.get_transactions_by_address(BTC_ADDRESS)

        assert len(legs) == 1
        leg = legs[0]
        assert leg.from_address == BTC_ADDRESS
        assert leg.to_address == BTC_ADDRESS_2
        # 90_000 sat == 0.0009 BTC; the 10_000 sat miner fee is NOT attributed
        # to the receiver, only recorded in metadata.
        assert leg.value == "0.0009"
        assert leg.metadata["value_sats"] == 90_000
        assert leg.metadata["fee_sats"] == 10_000
        assert leg.token_symbol == "BTC"
        assert leg.block_number == 800_000

    async def test_multi_input_multi_output_aggregates_into_expected_legs(self):
        """Two senders (A=100_000, B=60_000) funding two receivers
        (C=120_000, D=40_000) produce four proportionally attributed legs."""
        tx = _btc_tx(
            [
                _vin(BTC_ADDRESS, 40_000),
                _vin(BTC_ADDRESS, 60_000),  # same address twice -> summed to 100_000
                _vin(BTC_BECH32, 60_000),
            ],
            [
                _vout(BTC_ADDRESS_2, 120_000),
                _vout("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", 40_000),
            ],
        )
        provider = _bitcoin({f"/address/{BTC_ADDRESS}/txs": _json_route([tx])})

        legs = await provider.get_transactions_by_address(BTC_ADDRESS)

        # Only legs touching the queried address are returned to that wallet.
        by_pair = {(leg.from_address, leg.to_address): leg.metadata["value_sats"] for leg in legs}
        assert by_pair == {
            (BTC_ADDRESS, BTC_ADDRESS_2): 75_000,  # 120_000 * (100_000/160_000)
            (BTC_ADDRESS, "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"): 25_000,
        }
        assert {leg.value for leg in legs} == {"0.00075", "0.00025"}

    async def test_change_output_is_netted_out_not_reported_as_self_send(self):
        tx = _btc_tx(
            [_vin(BTC_ADDRESS, 100_000)],
            [_vout(BTC_ADDRESS_2, 60_000), _vout(BTC_ADDRESS, 39_000)],
            fee=1_000,
        )
        provider = _bitcoin({f"/address/{BTC_ADDRESS}/txs": _json_route([tx])})

        legs = await provider.get_transactions_by_address(BTC_ADDRESS)

        assert len(legs) == 1
        assert legs[0].from_address == BTC_ADDRESS
        assert legs[0].to_address == BTC_ADDRESS_2
        # Net spend is 61_000 sat, but only the 60_000 sat the counterparty
        # actually received is attributed; the 1_000 sat fee is not a leg.
        assert legs[0].metadata["value_sats"] == 60_000
        assert not any(leg.to_address == BTC_ADDRESS for leg in legs)

    async def test_coinbase_transaction_handled_without_crashing(self):
        tx = _btc_tx(
            [_vin(None, 0, coinbase=True)],
            [_vout(BTC_ADDRESS, 625_000_000)],
            txid="bb" * 32,
        )
        provider = _bitcoin({f"/address/{BTC_ADDRESS}/txs": _json_route([tx])})

        legs = await provider.get_transactions_by_address(BTC_ADDRESS)

        assert len(legs) == 1
        assert legs[0].from_address == COINBASE_SENDER
        assert legs[0].to_address == BTC_ADDRESS
        assert legs[0].value == "6.25"
        assert legs[0].metadata["is_coinbase"] is True
        assert legs[0].method == "coinbase"

    async def test_op_return_output_is_skipped(self):
        tx = _btc_tx(
            [_vin(BTC_ADDRESS, 50_000)],
            [_vout(BTC_ADDRESS_2, 49_000), _vout(None, 0)],
            fee=1_000,
        )
        provider = _bitcoin({f"/address/{BTC_ADDRESS}/txs": _json_route([tx])})

        legs = await provider.get_transactions_by_address(BTC_ADDRESS)

        assert len(legs) == 1
        assert legs[0].to_address == BTC_ADDRESS_2

    async def test_get_transaction_returns_first_mapped_leg(self):
        tx = _btc_tx([_vin(BTC_ADDRESS, 100_000)], [_vout(BTC_ADDRESS_2, 99_000)], fee=1_000)
        provider = _bitcoin({f"/tx/{'aa' * 32}": _json_route(tx)})

        leg = await provider.get_transaction("aa" * 32)

        assert leg is not None
        assert leg.tx_hash == "aa" * 32
        assert leg.metadata["leg_count_hint"] == 1


class TestBitcoinErrorHandling:
    async def test_tx_404_returns_none(self):
        provider = _bitcoin({f"/tx/{'cc' * 32}": _json_route({"error": "not found"}, status=404)})
        assert await provider.get_transaction("cc" * 32) is None

    async def test_address_404_surfaces_provider_error(self):
        provider = _bitcoin(
            {f"/address/{BTC_ADDRESS}/txs": _text_route("Invalid Bitcoin address", status=404)}
        )

        with pytest.raises(ExternalServiceError) as excinfo:
            await provider.get_transactions_by_address(BTC_ADDRESS)

        assert "404" in excinfo.value.message

    async def test_server_error_retried_then_raises(self):
        calls: list[int] = []

        def flaky(_request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(502, text="bad gateway")

        provider = _bitcoin({f"/address/{BTC_ADDRESS}/txs": flaky}, max_retries=2)

        with pytest.raises(ExternalServiceError):
            await provider.get_transactions_by_address(BTC_ADDRESS)

        assert len(calls) == 2

    async def test_invalid_address_rejected_before_any_http_call(self):
        provider = _bitcoin({})
        with pytest.raises(ExternalServiceError):
            await provider.get_transactions_by_address("garbage")


class TestBitcoinAccountData:
    async def test_get_wallet_balance_converts_satoshis(self):
        provider = _bitcoin(
            {
                f"/address/{BTC_ADDRESS}": _json_route(
                    {
                        "address": BTC_ADDRESS,
                        "chain_stats": {"funded_txo_sum": 250_000_000, "spent_txo_sum": 50_000_000},
                        "mempool_stats": {"funded_txo_sum": 0, "spent_txo_sum": 0},
                    }
                )
            }
        )

        balance = await provider.get_wallet_balance(BTC_ADDRESS)

        assert balance.eth_balance == "2"  # 200_000_000 sat == 2 BTC
        assert balance.chain == "Bitcoin"
        assert balance.tokens == []

    async def test_get_token_transfers_is_empty_by_design(self):
        provider = _bitcoin({})
        assert await provider.get_token_transfers(BTC_ADDRESS) == []

    async def test_validate_address_accepts_p2pkh_p2sh_bech32_rejects_garbage(self):
        provider = _bitcoin({})
        assert await provider.validate_address(BTC_ADDRESS) is True
        assert await provider.validate_address(BTC_ADDRESS_2) is True
        assert await provider.validate_address(BTC_BECH32) is True
        assert await provider.validate_address("garbage") is False
        assert await provider.validate_address("") is False
        # Valid shape, corrupted checksum (last char changed).
        assert await provider.validate_address(BTC_ADDRESS[:-1] + "b") is False

    async def test_latest_block_from_plain_text_tip(self):
        provider = _bitcoin({"/blocks/tip/height": _text_route("870123")})

        assert await provider.get_latest_block() == 870_123
        assert await provider.health_check() is True

    async def test_get_chain_info_and_identity(self):
        provider = _bitcoin({})
        info = await provider.get_chain_info()

        assert isinstance(info, ChainInfo)
        assert info.chain_id == BITCOIN_PSEUDO_CHAIN_ID == 2147483648
        assert info.symbol == "BTC"
        assert provider.chain_name == "Bitcoin"


# ---------------------------------------------------------------------------
# ABC conformance + factory registration
# ---------------------------------------------------------------------------


class TestAbstractInterfaceConformance:
    @pytest.mark.parametrize("provider_cls", [TronProvider, BitcoinProvider])
    def test_no_unimplemented_abstract_methods(self, provider_cls):
        assert issubclass(provider_cls, BlockchainProvider)
        assert not inspect.isabstract(provider_cls)
        assert getattr(provider_cls, "__abstractmethods__", frozenset()) == frozenset()

    @pytest.mark.parametrize("provider_cls", [TronProvider, BitcoinProvider])
    def test_implements_every_method_the_evm_providers_do(self, provider_cls):
        required = {
            name
            for name, value in vars(BlockchainProvider).items()
            if getattr(value, "__isabstractmethod__", False)
            or isinstance(value, property)
            and getattr(value.fget, "__isabstractmethod__", False)
        }
        assert required, "BlockchainProvider should declare abstract members"
        for name in required:
            assert hasattr(provider_cls, name), f"{provider_cls.__name__} is missing {name}"


class TestFactoryRegistration:
    @pytest.fixture(autouse=True)
    def _isolated_registry(self):
        # ProviderRegistry is process-global; snapshot and restore it so this
        # test never leaks providers into the rest of the suite.
        saved_providers = dict(ProviderRegistry._providers)
        saved_default = ProviderRegistry._default_provider
        saved_initialized = ProviderFactory._initialized
        ProviderRegistry._providers = {}
        ProviderRegistry._default_provider = None
        ProviderFactory._initialized = False
        yield
        ProviderRegistry._providers = saved_providers
        ProviderRegistry._default_provider = saved_default
        ProviderFactory._initialized = saved_initialized

    def test_factory_registers_tron_and_bitcoin(self):
        ProviderFactory.initialize()

        assert isinstance(ProviderFactory.get_provider_by_name("tron"), TronProvider)
        assert isinstance(ProviderFactory.get_provider_by_name("bitcoin"), BitcoinProvider)

    def test_factory_registers_them_under_their_chain_ids(self):
        ProviderFactory.initialize()

        assert isinstance(ProviderFactory.get_provider(TRON_MAINNET_CHAIN_ID), TronProvider)
        assert isinstance(ProviderFactory.get_provider(BITCOIN_PSEUDO_CHAIN_ID), BitcoinProvider)

    def test_lookup_by_name_is_case_insensitive(self):
        ProviderFactory.initialize()

        assert ProviderFactory.get_provider_by_name("TRON") is ProviderFactory.get_provider_by_name(
            "tron"
        )
        assert ProviderFactory.get_provider_by_name(
            "Bitcoin"
        ) is ProviderFactory.get_provider_by_name("bitcoin")
