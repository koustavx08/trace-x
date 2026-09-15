"""
Bitcoin blockchain provider backed by the public Blockstream Esplora REST API.

Why this module exists
----------------------
Bitcoin is the second-largest rail for Indian cybercrime cash-out after TRC-20
USDT (docs/KEY_IMPLEMENTATIONS_AND_ALGORITHMS.md section 3.1). Bitcoin has no
accounts, no JSON-RPC `eth_*` surface and no smart contracts, so it cannot
reuse `providers/evm/base.py`; this provider implements the
`BlockchainProvider` ABC directly so existing callers
(`services/wallet_analysis.py`, `api/v1/analysis.py`) consume BTC data through
exactly the same `BlockchainTransaction` / `WalletBalance` shapes as the EVM
chains.

THE UTXO -> ACCOUNT MAPPING (the part a reviewer will question)
---------------------------------------------------------------
A Bitcoin transaction is not a "from -> to" edge: it spends N inputs and
creates M outputs, and the rest of this application (graph edges, flow tracing,
risk scoring) is account-based and needs sender -> receiver legs. One BTC
transaction is therefore expanded into legs like this:

1. Sum input satoshis per address from `vin[].prevout.scriptpubkey_address`.
2. Sum output satoshis per address from `vout[].scriptpubkey_address`.
   Outputs with no address (OP_RETURN and other non-standard scripts) are
   skipped -- they are unspendable and not a destination.
3. Compute each address's NET position: `net = outputs - inputs`.
   Addresses with net < 0 are senders; net > 0 are receivers. Netting is what
   removes the change-output artefact: an address that puts in 1.0 BTC and gets
   0.4 BTC of change back is reported as sending 0.6 BTC, not as sending 1.0
   and receiving 0.4 from itself.
4. Attribute every receiver's gain across the senders in proportion to how much
   each sender contributed:
       leg(sender, receiver) = receiver_net * (sender_net / total_sender_net)
   Bitcoin genuinely does not record which input paid which output, so this
   proportional split is a documented estimate, not ground truth. The invariant
   it guarantees is that the legs into a receiver sum to exactly what that
   receiver gained, and that the miner fee -- the difference between total
   inputs and total outputs -- is NOT attributed to any receiver. The fee is
   recorded in `metadata["fee_sats"]` instead.
5. Satoshi amounts are converted to BTC (8 decimals) via `Decimal`; the exact
   satoshi integer is preserved in `metadata["value_sats"]`. Per-leg satoshi
   amounts are floored, so rounding can only under-report a leg by <1 satoshi
   and never invents value.

Coinbase (newly mined) transactions have an input with no previous output and
therefore no sender address. Those are not dropped: the synthetic sender
`COINBASE_SENDER` is used, and `metadata["is_coinbase"]` is set, so mined
coins still appear as an edge into the miner's address.

Other shape notes
-----------------
* `WalletBalance.eth_balance` is the ABC's native-balance field; for Bitcoin it
  carries the BTC balance (funded minus spent) in human units.
* Bitcoin's base layer has no fungible-token standard, so `get_token_transfers`
  honestly returns an empty list rather than pretending otherwise.
* Bitcoin has no EIP-155 chain id. `BITCOIN_PSEUDO_CHAIN_ID` (2147483648 =
  0x80000000, the BIP-44 hardened coin type for Bitcoin, SLIP-44 index 0) is
  used as the integer registry key, because `ProviderRegistry` is keyed by int.

Errors surface as `ExternalServiceError`, the repo's provider-failure
exception, so "Blockstream is down" is never mistaken for "this address has no
transactions". Transport errors, HTTP 429 and HTTP 5xx are retried with
exponential backoff (tenacity) first.
"""

import hashlib
from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.exceptions import ExternalServiceError

from .base import (
    BlockchainProvider,
    BlockchainTransaction,
    ChainInfo,
    WalletBalance,
)

logger = structlog.get_logger(__name__)

_SERVICE = "blockstream"

# See the module docstring: ProviderRegistry is keyed by int and Bitcoin has no
# chain id, so the BIP-44 hardened coin type (0x80000000 | 0) is used.
BITCOIN_PSEUDO_CHAIN_ID = 2147483648

SATOSHIS_PER_BTC = 100_000_000
BTC_DECIMALS = 8

# Synthetic sender for coinbase inputs, which have no funding address.
COINBASE_SENDER = "COINBASE"

_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_INDEX = {char: index for index, char in enumerate(_BASE58_ALPHABET)}
# Mainnet P2PKH (0x00 -> "1...") and P2SH (0x05 -> "3...") version bytes.
_BASE58_VERSIONS = {0x00, 0x05}


class _RetryableBitcoinError(ExternalServiceError):
    """Marker for Blockstream failures worth retrying (429 / 5xx).

    Subclasses `ExternalServiceError` so an exhausted retry budget still
    surfaces the repo's normal provider error type.
    """


def _bech32_polymod(values: list[int]) -> int:
    generator = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    checksum = 1
    for value in values:
        top = checksum >> 25
        checksum = ((checksum & 0x1FFFFFF) << 5) ^ value
        for index in range(5):
            checksum ^= generator[index] if ((top >> index) & 1) else 0
    return checksum


def _bech32_verify(address: str) -> bool:
    """Verify a bech32 (SegWit v0) or bech32m (Taproot) mainnet address."""
    if address.lower() != address and address.upper() != address:
        return False  # mixed case is invalid per BIP-173

    candidate = address.lower()
    if not candidate.startswith("bc1") or not 14 <= len(candidate) <= 74:
        return False

    hrp, _, data_part = candidate.partition("1")
    if not data_part or any(char not in _BECH32_CHARSET for char in data_part):
        return False

    expanded = [ord(char) >> 5 for char in hrp] + [0] + [ord(char) & 31 for char in hrp]
    data = [_BECH32_CHARSET.index(char) for char in data_part]
    checksum = _bech32_polymod(expanded + data)
    # 1 = bech32 (witness v0), 0x2BC830A3 = bech32m (witness v1+).
    return checksum in (1, 0x2BC830A3)


def _base58check_verify(address: str) -> bool:
    number = 0
    for char in address:
        index = _BASE58_INDEX.get(char)
        if index is None:
            return False
        number = number * 58 + index

    raw = number.to_bytes((number.bit_length() + 7) // 8, "big")
    raw = b"\x00" * (len(address) - len(address.lstrip("1"))) + raw
    if len(raw) != 25:
        return False

    payload, checksum = raw[:-4], raw[-4:]
    if hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] != checksum:
        return False
    return payload[0] in _BASE58_VERSIONS


def is_valid_bitcoin_address(address: str) -> bool:
    """True for a well-formed Bitcoin mainnet address (P2PKH, P2SH, bech32,
    bech32m). Base58 addresses are case-sensitive and are never lowercased."""
    if not address:
        return False
    if address.lower().startswith("bc1"):
        return _bech32_verify(address)
    if address[0] in ("1", "3") and 26 <= len(address) <= 35:
        return _base58check_verify(address)
    return False


def _sats_to_btc(satoshis: int) -> str:
    """Exact satoshi -> BTC conversion. `Decimal`, never float: 0.1 + 0.2 style
    drift is unacceptable in an evidence trail."""
    value = Decimal(satoshis) / Decimal(SATOSHIS_PER_BTC)
    return format(value.normalize(), "f")


class BitcoinProvider(BlockchainProvider):
    BASE_URL = "https://blockstream.info/api"
    EXPLORER_URL = "https://blockstream.info"

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        # Blockstream's public Esplora instance needs no API key, so there is
        # deliberately no settings lookup and no ProviderNotConfiguredError
        # path here -- this provider is always available.
        self._base_url = (base_url or self.BASE_URL).rstrip("/")
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._retry_backoff = retry_backoff

        self._http_client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Accept": "application/json"},
            transport=transport,
        )

    @property
    def chain_id(self) -> int:
        return BITCOIN_PSEUDO_CHAIN_ID

    @property
    def chain_name(self) -> str:
        return "Bitcoin"

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------

    async def _request(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        as_text: bool = False,
        allow_404: bool = False,
    ) -> Any:
        url = f"{self._base_url}{path}"

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=self._retry_backoff, max=4.0),
            retry=retry_if_exception_type((httpx.TransportError, _RetryableBitcoinError)),
            reraise=True,
        ):
            with attempt:
                try:
                    response = await self._http_client.get(url, params=params)
                except httpx.TransportError:
                    logger.warning("blockstream_transport_error", path=path)
                    raise

                if response.status_code == 404 and allow_404:
                    return None

                if response.status_code == 429 or response.status_code >= 500:
                    logger.warning(
                        "blockstream_retryable_status", path=path, status=response.status_code
                    )
                    raise _RetryableBitcoinError(
                        service=_SERVICE,
                        message=f"Blockstream returned HTTP {response.status_code} for {path}",
                        details={"service": _SERVICE, "path": path},
                    )

                if response.status_code >= 400:
                    raise ExternalServiceError(
                        service=_SERVICE,
                        message=f"Blockstream returned HTTP {response.status_code} for {path}",
                        details={"service": _SERVICE, "path": path},
                    )

                if as_text:
                    return response.text.strip()

                try:
                    return response.json()
                except ValueError as exc:
                    raise ExternalServiceError(
                        service=_SERVICE,
                        message=f"Blockstream returned a non-JSON body for {path}",
                        details={"service": _SERVICE, "path": path},
                    ) from exc

        # Unreachable: AsyncRetrying(reraise=True) either returns or raises.
        raise ExternalServiceError(service=_SERVICE, message=f"Blockstream request failed: {path}")

    # ------------------------------------------------------------------
    # UTXO -> account mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate_sides(tx: dict[str, Any]) -> tuple[dict[str, int], dict[str, int], bool]:
        """Sum satoshis per address on each side of the transaction.

        Returns (inputs_by_address, outputs_by_address, is_coinbase).
        """
        inputs: dict[str, int] = defaultdict(int)
        outputs: dict[str, int] = defaultdict(int)
        is_coinbase = False

        for vin in tx.get("vin") or []:
            if vin.get("is_coinbase"):
                is_coinbase = True
                continue
            prevout = vin.get("prevout") or {}
            address = prevout.get("scriptpubkey_address")
            if not address:
                # A spent output with no decodable address still moved value;
                # bucket it under the synthetic sender so the amounts stay
                # balanced instead of silently vanishing.
                address = COINBASE_SENDER
            inputs[address] += int(prevout.get("value") or 0)

        for vout in tx.get("vout") or []:
            address = vout.get("scriptpubkey_address")
            if not address:
                continue  # OP_RETURN / non-standard: unspendable, not a destination
            outputs[address] += int(vout.get("value") or 0)

        return dict(inputs), dict(outputs), is_coinbase

    def _map_utxo_to_legs(self, tx: dict[str, Any]) -> list[BlockchainTransaction]:
        """Expand one UTXO transaction into account-style sender -> receiver legs.

        See the module docstring for the full algorithm and its caveats.
        """
        inputs, outputs, is_coinbase = self._aggregate_sides(tx)

        total_in = sum(inputs.values())
        total_out = sum(outputs.values())
        # Blockstream reports `fee`; for a coinbase tx it is 0 and total_in is 0.
        fee_sats = int(tx.get("fee") or max(total_in - total_out, 0))

        net: dict[str, int] = defaultdict(int)
        for address, amount in inputs.items():
            net[address] -= amount
        for address, amount in outputs.items():
            net[address] += amount

        senders = {address: -amount for address, amount in net.items() if amount < 0}
        receivers = {address: amount for address, amount in net.items() if amount > 0}

        if is_coinbase and not senders:
            # Newly mined coins have no funding address at all. Attribute the
            # whole output side to the synthetic coinbase sender so the miner's
            # address still gets an inbound edge.
            senders = {COINBASE_SENDER: sum(receivers.values())}

        if not senders or not receivers:
            # e.g. a self-send whose only outputs are change, or an OP_RETURN-only
            # transaction: no cross-address value movement to report.
            return []

        status = tx.get("status") or {}
        block_number = int(status.get("block_height") or 0)
        block_time = status.get("block_time")
        timestamp = (
            datetime.fromtimestamp(block_time, tz=UTC).replace(tzinfo=None)
            if block_time
            else datetime.now(UTC).replace(tzinfo=None)
        )
        tx_hash = tx.get("txid", "")
        total_sender_sats = sum(senders.values())

        legs: list[BlockchainTransaction] = []
        leg_index = 0
        for receiver, received_sats in sorted(receivers.items()):
            for sender, sent_sats in sorted(senders.items()):
                share = (
                    Decimal(received_sats) * Decimal(sent_sats) / Decimal(total_sender_sats)
                ).quantize(Decimal(1), rounding=ROUND_DOWN)
                leg_sats = int(share)
                if leg_sats <= 0:
                    continue

                legs.append(
                    BlockchainTransaction(
                        tx_hash=tx_hash,
                        block_number=block_number,
                        timestamp=timestamp,
                        from_address=sender,
                        to_address=receiver,
                        value=_sats_to_btc(leg_sats),
                        token_symbol="BTC",
                        token_decimals=BTC_DECIMALS,
                        method="coinbase" if is_coinbase else "utxo_transfer",
                        status=1 if status.get("confirmed", True) else 0,
                        metadata={
                            "chain": "bitcoin",
                            "value_sats": leg_sats,
                            "leg_index": leg_index,
                            "leg_count_hint": len(senders) * len(receivers),
                            "is_coinbase": is_coinbase,
                            "fee_sats": fee_sats,
                            "total_input_sats": total_in,
                            "total_output_sats": total_out,
                            # Flag that this leg is a proportional estimate: UTXO
                            # inputs are not bound to specific outputs on-chain.
                            "attribution": "proportional",
                        },
                    )
                )
                leg_index += 1

        return legs

    # ------------------------------------------------------------------
    # BlockchainProvider interface
    # ------------------------------------------------------------------

    async def get_latest_block(self) -> int:
        height = await self._request("/blocks/tip/height", as_text=True)
        try:
            return int(height)
        except (TypeError, ValueError) as exc:
            raise ExternalServiceError(
                service=_SERVICE,
                message=f"Blockstream returned a non-numeric chain tip: {height!r}",
                details={"service": _SERVICE},
            ) from exc

    async def get_block(self, block_number: int) -> dict[str, Any] | None:
        try:
            block_hash = await self._request(
                f"/block-height/{block_number}", as_text=True, allow_404=True
            )
            if not block_hash:
                return None
            block = await self._request(f"/block/{block_hash}", allow_404=True)
        except ExternalServiceError as exc:
            logger.warning(
                "bitcoin_get_block_failed", block_number=block_number, error=exc.message
            )
            return None
        return block if block else None

    async def get_transaction(self, tx_hash: str) -> BlockchainTransaction | None:
        """Return the FIRST mapped leg of a UTXO transaction.

        The ABC promises a single transaction object, but one BTC transaction is
        many account-style legs. The first leg (receivers and senders ordered by
        address) is returned, and `metadata["leg_count_hint"]` tells the caller
        how many legs exist; callers needing all of them use
        `get_transactions_by_address`.
        """
        tx = await self._request(f"/tx/{tx_hash}", allow_404=True)
        if not tx:
            return None

        legs = self._map_utxo_to_legs(tx)
        return legs[0] if legs else None

    async def get_transactions_by_address(
        self,
        address: str,
        start_block: int = 0,
        end_block: int | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> list[BlockchainTransaction]:
        if not is_valid_bitcoin_address(address):
            raise ExternalServiceError(
                service=_SERVICE,
                message=f"Invalid Bitcoin address: {address}",
                details={"service": _SERVICE, "address": address},
            )

        raw_txs = await self._request(f"/address/{address}/txs") or []

        legs: list[BlockchainTransaction] = []
        for tx in raw_txs:
            for leg in self._map_utxo_to_legs(tx):
                # Esplora has no block-range query, so the ABC's window is
                # applied client-side. Height 0 means unconfirmed (mempool).
                if leg.block_number:
                    if leg.block_number < start_block:
                        continue
                    if end_block is not None and leg.block_number > end_block:
                        continue
                # Only legs that actually touch the queried address are relevant
                # to that wallet's account view.
                if address not in (leg.from_address, leg.to_address):
                    continue
                legs.append(leg)

        offset = max(0, (max(page, 1) - 1) * page_size)
        paged = legs[offset : offset + page_size]

        logger.info(
            "bitcoin_transactions_fetched",
            address=address,
            transactions=len(raw_txs),
            legs=len(legs),
            returned=len(paged),
        )
        return paged

    async def get_wallet_balance(self, address: str) -> WalletBalance:
        stats = await self._request(f"/address/{address}")
        chain_stats = (stats or {}).get("chain_stats") or {}
        mempool_stats = (stats or {}).get("mempool_stats") or {}

        confirmed = int(chain_stats.get("funded_txo_sum") or 0) - int(
            chain_stats.get("spent_txo_sum") or 0
        )
        unconfirmed = int(mempool_stats.get("funded_txo_sum") or 0) - int(
            mempool_stats.get("spent_txo_sum") or 0
        )

        return WalletBalance(
            address=address,
            chain=self.chain_name,
            eth_balance=_sats_to_btc(confirmed),
            # Bitcoin's base layer has no fungible-token standard, so this is
            # honestly and permanently empty (see module docstring).
            tokens=[],
            last_updated=datetime.now(UTC).replace(tzinfo=None),
        )

    async def get_token_transfers(
        self,
        address: str,
        token_address: str | None = None,
        start_block: int = 0,
        end_block: int | None = None,
    ) -> list[BlockchainTransaction]:
        """Always empty: Bitcoin's base layer has no fungible-token standard.

        Not a stub -- there is genuinely nothing to fetch. Anything token-like on
        Bitcoin (Omni, BRC-20/ordinals) is a separate protocol layer that
        Blockstream's Esplora API does not index, so returning [] is the honest
        answer rather than inventing data.
        """
        logger.debug("bitcoin_token_transfers_not_applicable", address=address)
        return []

    async def validate_address(self, address: str) -> bool:
        return is_valid_bitcoin_address(address)

    async def get_chain_info(self) -> ChainInfo:
        return ChainInfo(
            chain_id=BITCOIN_PSEUDO_CHAIN_ID,
            name=self.chain_name,
            symbol="BTC",
            rpc_url=self._base_url,
            explorer_url=self.EXPLORER_URL,
        )

    async def health_check(self) -> bool:
        try:
            return await self.get_latest_block() > 0
        except Exception:
            return False

    async def close(self) -> None:
        await self._http_client.aclose()
