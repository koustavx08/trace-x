"""Shared value types for the forensic analytics engines.

Every engine in this package (taint, clustering, flow, motif, correlation)
works off the same flat transfer record instead of talking to Neo4j or
Postgres itself. Keeping the engines pure makes them testable without a
database and lets a caller feed them rows from either store -- the graph
repository, the `transactions` table, or a provider response -- as long as it
normalises to `Transfer` first.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


def normalize_address(address: str) -> str:
    """Addresses are compared as lowercase everywhere in this codebase.

    EVM addresses are case-insensitive (EIP-55 checksums are display-only) and
    the graph layer already writes them lowercased. Tron (base58) and Bitcoin
    addresses ARE case-sensitive, so they are left alone: lowercasing them
    would produce an address that does not exist on-chain.
    """
    stripped = address.strip()
    if stripped.startswith("0x") or stripped.startswith("0X"):
        return stripped.lower()
    return stripped


def as_utc(moment: datetime) -> datetime:
    """Treat a naive timestamp as UTC, which is what every producer writes."""
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment


@dataclass(frozen=True, slots=True)
class Transfer:
    """One value movement between two addresses.

    `value_usd` is the fiat-normalised amount: the engines reason about money,
    not token units, so a USDT hop and an ETH hop can be compared on one graph.
    """

    tx_hash: str
    from_address: str
    to_address: str
    value_usd: float
    timestamp: datetime
    chain: str = "ethereum"
    asset: str = "ETH"
    block_number: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "from_address", normalize_address(self.from_address))
        object.__setattr__(self, "to_address", normalize_address(self.to_address))
        object.__setattr__(self, "timestamp", as_utc(self.timestamp))


@dataclass(frozen=True, slots=True)
class FiatPayment:
    """A bank-rail leg (UPI / IMPS / NEFT) from a 1930 / I4C complaint record.

    Used by the P2P correlator to tie a victim's fiat transfer to the on-chain
    escrow release it paid for.
    """

    reference_id: str
    payer_account: str
    payee_account: str
    amount_inr: float
    timestamp: datetime
    rail: str = "UPI"

    def __post_init__(self) -> None:
        object.__setattr__(self, "timestamp", as_utc(self.timestamp))


__all__ = ["Transfer", "FiatPayment", "normalize_address", "as_utc"]
