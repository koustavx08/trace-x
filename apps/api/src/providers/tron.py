"""
TRON blockchain provider backed by the public TronGrid REST API.

Why this module exists
----------------------
Over 70% of Indian cybercrime fund movement is TRC-20 USDT on TRON
(docs/KEY_IMPLEMENTATIONS_AND_ALGORITHMS.md section 3.1), which makes TRON the
single highest-value chain gap in the product. TRON is *not* EVM-JSON-RPC
compatible (no `eth_*` methods, different address encoding, different tx
envelope), so it cannot reuse `providers/evm/base.py`. This provider therefore
implements the `BlockchainProvider` ABC directly over TronGrid REST, so every
existing caller (`services/wallet_analysis.py`, `api/v1/analysis.py`) keeps
working against the same Transaction/Wallet shapes with no changes.

Shape-compatibility notes (the parts a reviewer will question)
--------------------------------------------------------------
* `WalletBalance.eth_balance` is the ABC's *native* balance field. For TRON it
  carries the TRX balance in human units. The field name is EVM-centric, but it
  is reused rather than renamed so callers need no special-casing.
* `BlockchainTransaction.value` is emitted in HUMAN units for both TRX and
  TRC-20. TRX has 6 decimals (SUN), and USDT-TRC20 also has 6 decimals -- NOT
  18. Token decimals are always taken from TronGrid's `token_info.decimals`
  when present and only fall back to a small known-token table, never to an
  18-decimal assumption. The raw base-unit integer is preserved in
  `metadata["raw_value"]` so nothing is lost.
* TRON addresses are base58check ("T...") and are CASE-SENSITIVE. They are
  never lowercased and never checksum-cased (there is no EIP-55 here).
  TronGrid can answer with 21-byte hex ("41...") addresses depending on the
  endpoint and the `visible` flag, so hex addresses are converted back to
  base58check here -- the rest of the app only ever sees one address format.
* TronGrid's TRC-20 endpoint returns `block_timestamp` but no block height, so
  `block_number` is 0 on TRC-20 transfers; order those by `timestamp`. Native
  transactions do carry `blockNumber` and are filtered by it.
* TronGrid pages with an opaque `fingerprint` cursor rather than numeric pages,
  so the ABC's `page` argument is honoured by walking that cursor forward.

Errors are raised as `ExternalServiceError` (the repo's provider-failure
exception) rather than being swallowed into an empty list, so an investigator
never mistakes "TronGrid is down" for "this wallet has no transactions".
Transport failures, HTTP 429 and HTTP 5xx are retried with exponential backoff
(tenacity) before that error is raised.
"""

import hashlib
import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.config import get_settings
from src.core.exceptions import ExternalServiceError

from .base import (
    BlockchainProvider,
    BlockchainTransaction,
    ChainInfo,
    WalletBalance,
)

logger = structlog.get_logger(__name__)

_SERVICE = "trongrid"

# TRON has no EIP-155 chain id in the EVM sense, but 728126428 is the value
# TRON mainnet reports to EVM-compatible tooling (and what Chainlist/TronLink
# use), so it is the natural integer key for `ProviderRegistry`.
TRON_MAINNET_CHAIN_ID = 728126428

# Tether USD on TRON. Hardcoded only as a decimals/symbol fallback for
# endpoints that omit `token_info` (e.g. a raw TriggerSmartContract call).
USDT_TRC20_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
_KNOWN_TOKENS: dict[str, tuple[str, int]] = {USDT_TRC20_CONTRACT: ("USDT", 6)}

# TRX itself is denominated in SUN: 1 TRX = 1_000_000 SUN.
TRX_DECIMALS = 6

# keccak256("transfer(address,uint256)")[:4] -- the on-chain call that emits the
# TRC-20 `Transfer(address,address,uint256)` log we care about.
_TRC20_TRANSFER_SELECTOR = "a9059cbb"

_TRON_ADDRESS_PREFIX = 0x41
_MAX_PAGE_SIZE = 200

_B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {char: index for index, char in enumerate(_B58_ALPHABET)}


class _RetryableTronError(ExternalServiceError):
    """Marker for TronGrid failures worth retrying (429 / 5xx).

    Subclassing `ExternalServiceError` means that if every retry is exhausted
    the caller still sees the repo's normal provider error type.
    """


def _b58check_decode(value: str) -> bytes | None:
    """Decode a base58check string, returning its payload or None if the
    alphabet/checksum is wrong. Case is significant and preserved."""
    number = 0
    for char in value:
        index = _B58_INDEX.get(char)
        if index is None:
            return None
        number = number * 58 + index

    raw = number.to_bytes((number.bit_length() + 7) // 8, "big")
    leading_zeros = len(value) - len(value.lstrip("1"))
    raw = b"\x00" * leading_zeros + raw
    if len(raw) < 5:
        return None

    payload, checksum = raw[:-4], raw[-4:]
    if hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] != checksum:
        return None
    return payload


def _b58check_encode(payload: bytes) -> str:
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    raw = payload + checksum
    number = int.from_bytes(raw, "big")

    encoded = ""
    while number > 0:
        number, remainder = divmod(number, 58)
        encoded = _B58_ALPHABET[remainder] + encoded

    leading_zeros = len(raw) - len(raw.lstrip(b"\x00"))
    return "1" * leading_zeros + encoded


def is_valid_tron_address(address: str) -> bool:
    """True for a well-formed base58check TRON mainnet address.

    Deliberately case-sensitive: base58 uses mixed case and the checksum is
    computed over the decoded bytes, so lowercasing a TRON address silently
    turns it into a different (invalid) address.
    """
    if not address or not address.startswith("T") or len(address) != 34:
        return False
    payload = _b58check_decode(address)
    return payload is not None and len(payload) == 21 and payload[0] == _TRON_ADDRESS_PREFIX


def normalize_tron_address(address: str | None) -> str:
    """Return a base58check ("T...") address for either encoding TronGrid may
    hand back. Hex "41..." addresses are re-encoded; anything already base58 is
    returned untouched (never lowercased)."""
    if not address:
        return ""

    candidate = address.strip()
    if candidate.startswith("0x"):
        candidate = candidate[2:]

    # A 42-char hex string beginning with the 0x41 TRON prefix is the raw form.
    if len(candidate) == 42 and candidate.lower().startswith("41"):
        try:
            return _b58check_encode(bytes.fromhex(candidate))
        except ValueError:
            return address
    return address


def _format_units(raw_value: int | str, decimals: int) -> str:
    """Convert a base-unit integer to a human-unit decimal string.

    `Decimal` (not float) because a 6-decimal USDT amount of e.g. 1234567891234
    must round-trip exactly in an evidence trail.
    """
    try:
        amount = Decimal(str(raw_value))
    except (ArithmeticError, ValueError):
        return "0"
    scaled = amount / (Decimal(10) ** decimals)
    return format(scaled.normalize(), "f")


def _utc_from_millis(timestamp_ms: int | None) -> datetime:
    """TronGrid timestamps are epoch milliseconds. Naive-UTC datetimes are
    returned to match what the EVM providers emit."""
    if not timestamp_ms:
        return datetime.now(UTC).replace(tzinfo=None)
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).replace(tzinfo=None)


class TronProvider(BlockchainProvider):
    BASE_URL = "https://api.trongrid.io"
    EXPLORER_URL = "https://tronscan.org"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        settings = get_settings()
        # TRON_API_KEY is optional (TronGrid serves anonymous traffic at a lower
        # rate limit) and is read defensively: `Settings` uses extra="ignore",
        # so an env-only key never becomes an attribute -- hence the os.environ
        # fallback. This keeps the provider usable without editing config.py.
        self._api_key = (
            api_key
            if api_key is not None
            else getattr(settings, "TRON_API_KEY", None) or os.environ.get("TRON_API_KEY")
        )

        self._base_url = (base_url or self.BASE_URL).rstrip("/")
        self._timeout = timeout
        self._max_retries = max(1, max_retries)
        self._retry_backoff = retry_backoff

        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["TRON-PRO-API-KEY"] = self._api_key

        self._http_client = httpx.AsyncClient(
            timeout=timeout, headers=headers, transport=transport
        )

    @property
    def chain_id(self) -> int:
        return TRON_MAINNET_CHAIN_ID

    @property
    def chain_name(self) -> str:
        return "Tron"

    # ------------------------------------------------------------------
    # HTTP plumbing
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        allow_404: bool = False,
    ) -> Any:
        url = f"{self._base_url}{path}"

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=self._retry_backoff, max=4.0),
            retry=retry_if_exception_type((httpx.TransportError, _RetryableTronError)),
            reraise=True,
        ):
            with attempt:
                try:
                    response = await self._http_client.request(
                        method, url, params=params, json=json_body
                    )
                except httpx.TransportError:
                    logger.warning("trongrid_transport_error", path=path)
                    raise

                if response.status_code == 404 and allow_404:
                    return None

                if response.status_code == 429 or response.status_code >= 500:
                    logger.warning(
                        "trongrid_retryable_status", path=path, status=response.status_code
                    )
                    raise _RetryableTronError(
                        service=_SERVICE,
                        message=f"TronGrid returned HTTP {response.status_code} for {path}",
                        details={"service": _SERVICE, "path": path},
                    )

                if response.status_code >= 400:
                    raise ExternalServiceError(
                        service=_SERVICE,
                        message=f"TronGrid returned HTTP {response.status_code} for {path}",
                        details={"service": _SERVICE, "path": path},
                    )

                try:
                    return response.json()
                except ValueError as exc:
                    raise ExternalServiceError(
                        service=_SERVICE,
                        message=f"TronGrid returned a non-JSON body for {path}",
                        details={"service": _SERVICE, "path": path},
                    ) from exc

        # Unreachable: AsyncRetrying(reraise=True) either returns or raises.
        raise ExternalServiceError(service=_SERVICE, message=f"TronGrid request failed: {path}")

    async def _fetch_account_page(
        self, path: str, params: dict[str, Any], page: int, page_size: int
    ) -> list[dict[str, Any]]:
        """Fetch one logical page from a TronGrid v1 account endpoint.

        TronGrid pages with an opaque `fingerprint` cursor, so page N is reached
        by walking the cursor forward N-1 times.
        """
        query = dict(params)
        query["limit"] = max(1, min(page_size, _MAX_PAGE_SIZE))

        target_page = max(1, page)
        data: list[dict[str, Any]] = []

        for current_page in range(1, target_page + 1):
            payload = await self._request("GET", path, params=query)
            if isinstance(payload, dict) and payload.get("success") is False:
                raise ExternalServiceError(
                    service=_SERVICE,
                    message=f"TronGrid rejected the request for {path}",
                    details={"service": _SERVICE, "error": payload.get("error")},
                )

            data = (payload or {}).get("data") or []
            if current_page == target_page:
                break

            fingerprint = ((payload or {}).get("meta") or {}).get("fingerprint")
            if not fingerprint:
                # Fewer pages exist than were asked for.
                return []
            query["fingerprint"] = fingerprint

        return data

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _token_fallback(self, contract_address: str) -> tuple[str | None, int | None]:
        symbol, decimals = _KNOWN_TOKENS.get(contract_address, (None, None))
        return symbol, decimals

    def _parse_trc20_transfer(self, entry: dict[str, Any]) -> BlockchainTransaction:
        token_info = entry.get("token_info") or {}
        contract_address = normalize_tron_address(token_info.get("address"))
        symbol = token_info.get("symbol")
        decimals = token_info.get("decimals")

        if symbol is None or decimals is None:
            fallback_symbol, fallback_decimals = self._token_fallback(contract_address)
            symbol = symbol or fallback_symbol
            decimals = fallback_decimals if decimals is None else decimals

        raw_value = str(entry.get("value", "0"))
        # decimals may legitimately be 0; only an unknown token has None, and in
        # that case the raw base-unit integer is surfaced verbatim rather than
        # being scaled by a guessed exponent.
        human_value = _format_units(raw_value, int(decimals)) if decimals is not None else raw_value

        return BlockchainTransaction(
            tx_hash=entry.get("transaction_id", ""),
            # TronGrid's TRC-20 endpoint carries no block height; order by timestamp.
            block_number=int(entry.get("block") or 0),
            timestamp=_utc_from_millis(entry.get("block_timestamp")),
            from_address=normalize_tron_address(entry.get("from")),
            to_address=normalize_tron_address(entry.get("to")),
            value=human_value,
            token_address=contract_address or None,
            token_symbol=symbol,
            token_decimals=int(decimals) if decimals is not None else None,
            method="transfer",
            status=1,
            metadata={
                "chain": "tron",
                "transfer_type": "trc20",
                "raw_value": raw_value,
                "decimals_known": decimals is not None,
            },
        )

    def _decode_trc20_call(self, data_hex: str) -> tuple[str, int] | None:
        """Decode a `transfer(address,uint256)` calldata blob.

        Layout: 4-byte selector, then a 32-byte recipient (TRON keeps the same
        ABI encoding as the EVM, with the 21-byte address right-aligned and its
        0x41 prefix dropped), then a 32-byte amount.
        """
        payload = (data_hex or "").removeprefix("0x")
        if not payload.lower().startswith(_TRC20_TRANSFER_SELECTOR) or len(payload) < 136:
            return None
        try:
            recipient_hex = "41" + payload[8:72][-40:]
            amount = int(payload[72:136], 16)
        except ValueError:
            return None
        return normalize_tron_address(recipient_hex), amount

    def _parse_native_transaction(self, entry: dict[str, Any]) -> BlockchainTransaction | None:
        raw_data = entry.get("raw_data") or {}
        contracts = raw_data.get("contract") or []
        if not contracts:
            return None

        contract = contracts[0]
        contract_type = contract.get("type")
        value_map = (contract.get("parameter") or {}).get("value") or {}

        ret = (entry.get("ret") or [{}])[0]
        status = 1 if ret.get("contractRet", "SUCCESS") == "SUCCESS" else 0
        timestamp = _utc_from_millis(entry.get("block_timestamp") or raw_data.get("timestamp"))
        block_number = int(entry.get("blockNumber") or 0)
        owner = normalize_tron_address(value_map.get("owner_address"))

        if contract_type == "TransferContract":
            amount = int(value_map.get("amount") or 0)
            return BlockchainTransaction(
                tx_hash=entry.get("txID", ""),
                block_number=block_number,
                timestamp=timestamp,
                from_address=owner,
                to_address=normalize_tron_address(value_map.get("to_address")),
                value=_format_units(amount, TRX_DECIMALS),
                token_symbol="TRX",
                token_decimals=TRX_DECIMALS,
                method="TransferContract",
                status=status,
                metadata={"chain": "tron", "transfer_type": "trx", "raw_value": str(amount)},
            )

        if contract_type == "TriggerSmartContract":
            decoded = self._decode_trc20_call(value_map.get("data", ""))
            if not decoded:
                return None
            recipient, amount = decoded
            contract_address = normalize_tron_address(value_map.get("contract_address"))
            symbol, decimals = self._token_fallback(contract_address)
            human_value = _format_units(amount, decimals) if decimals is not None else str(amount)
            return BlockchainTransaction(
                tx_hash=entry.get("txID", ""),
                block_number=block_number,
                timestamp=timestamp,
                from_address=owner,
                to_address=recipient,
                value=human_value,
                token_address=contract_address or None,
                token_symbol=symbol,
                token_decimals=decimals,
                method="transfer",
                status=status,
                metadata={
                    "chain": "tron",
                    "transfer_type": "trc20",
                    "raw_value": str(amount),
                    "decimals_known": decimals is not None,
                },
            )

        return None

    # ------------------------------------------------------------------
    # BlockchainProvider interface
    # ------------------------------------------------------------------

    async def get_latest_block(self) -> int:
        payload = await self._request("POST", "/wallet/getnowblock", json_body={})
        header = (payload or {}).get("block_header") or {}
        return int((header.get("raw_data") or {}).get("number") or 0)

    async def get_block(self, block_number: int) -> dict[str, Any] | None:
        try:
            payload = await self._request(
                "POST", "/wallet/getblockbynum", json_body={"num": block_number}
            )
        except ExternalServiceError as exc:
            logger.warning("tron_get_block_failed", block_number=block_number, error=exc.message)
            return None
        # TronGrid answers an unknown height with `{}` rather than a 404.
        return payload if payload else None

    async def get_transaction(self, tx_hash: str) -> BlockchainTransaction | None:
        payload = await self._request(
            "POST",
            "/wallet/gettransactionbyid",
            json_body={"value": tx_hash, "visible": True},
            allow_404=True,
        )
        if not payload:
            return None

        payload.setdefault("txID", tx_hash)
        return self._parse_native_transaction(payload)

    async def get_transactions_by_address(
        self,
        address: str,
        start_block: int = 0,
        end_block: int | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> list[BlockchainTransaction]:
        if not is_valid_tron_address(address):
            raise ExternalServiceError(
                service=_SERVICE,
                message=f"Invalid TRON address: {address}",
                details={"service": _SERVICE, "address": address},
            )

        entries = await self._fetch_account_page(
            f"/v1/accounts/{address}/transactions",
            {"only_confirmed": "true", "visible": "true", "order_by": "block_timestamp,desc"},
            page,
            page_size,
        )

        transactions: list[BlockchainTransaction] = []
        for entry in entries:
            parsed = self._parse_native_transaction(entry)
            if parsed is None:
                continue
            # TronGrid filters by timestamp, not block height, so the ABC's
            # block window is applied client-side against `blockNumber`.
            if parsed.block_number:
                if parsed.block_number < start_block:
                    continue
                if end_block is not None and parsed.block_number > end_block:
                    continue
            transactions.append(parsed)

        logger.info(
            "tron_transactions_fetched",
            address=address,
            fetched=len(entries),
            parsed=len(transactions),
        )
        return transactions

    async def get_wallet_balance(self, address: str) -> WalletBalance:
        payload = await self._request("GET", f"/v1/accounts/{address}", params={"visible": "true"})
        records = (payload or {}).get("data") or []
        account = records[0] if records else {}

        trx_balance = _format_units(int(account.get("balance") or 0), TRX_DECIMALS)

        tokens: list[dict[str, Any]] = []
        for holding in account.get("trc20") or []:
            for contract_address, raw_balance in holding.items():
                normalized = normalize_tron_address(contract_address)
                symbol, decimals = self._token_fallback(normalized)
                tokens.append(
                    {
                        "contract_address": normalized,
                        "symbol": symbol,
                        "name": symbol,
                        "decimals": decimals,
                        # Unknown tokens keep their raw base-unit balance rather
                        # than being scaled by a guessed number of decimals.
                        "balance": _format_units(raw_balance, decimals)
                        if decimals is not None
                        else str(raw_balance),
                        "raw_balance": str(raw_balance),
                    }
                )

        return WalletBalance(
            address=address,
            chain=self.chain_name,
            eth_balance=trx_balance,
            tokens=tokens,
            last_updated=datetime.now(UTC).replace(tzinfo=None),
        )

    async def get_token_transfers(
        self,
        address: str,
        token_address: str | None = None,
        start_block: int = 0,
        end_block: int | None = None,
    ) -> list[BlockchainTransaction]:
        if not is_valid_tron_address(address):
            raise ExternalServiceError(
                service=_SERVICE,
                message=f"Invalid TRON address: {address}",
                details={"service": _SERVICE, "address": address},
            )

        params: dict[str, Any] = {"only_confirmed": "true"}
        if token_address:
            params["contract_address"] = token_address

        entries = await self._fetch_account_page(
            f"/v1/accounts/{address}/transactions/trc20", params, page=1, page_size=_MAX_PAGE_SIZE
        )

        transfers = [
            self._parse_trc20_transfer(entry)
            for entry in entries
            if entry.get("type", "Transfer") == "Transfer"
        ]

        logger.info("tron_trc20_transfers_fetched", address=address, count=len(transfers))
        return transfers

    async def validate_address(self, address: str) -> bool:
        return is_valid_tron_address(address)

    async def get_chain_info(self) -> ChainInfo:
        return ChainInfo(
            chain_id=TRON_MAINNET_CHAIN_ID,
            name=self.chain_name,
            symbol="TRX",
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
