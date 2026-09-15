"""Taint propagation over a flat list of transfers (blueprint 2.1).

Dijkstra answers "is B reachable from A", which is not the question an
investigator has to answer in court. When a thief mixes $75k of stolen funds
with $25k of clean liquidity and forwards $50k onward, the recovery claim
turns on *how much* of that $50k is provably the victim's money. This module
computes that number under the two models the industry (and every asset
recovery expert report) recognises:

* **Haircut (pro-rata)** -- every dollar leaving a wallet carries the wallet's
  current taint percentage. Conservative and largely order-insensitive, which
  is why it is the model most regulators and exchanges accept.
* **FIFO (poison)** -- value is consumed oldest-lot-first, so the first
  dollars out are the first dollars in. It produces very different answers
  when a launderer deliberately parks clean funds in a wallet before the
  stolen ones arrive.

The two models are kept side by side on purpose: a wallet whose taint differs
wildly between them is itself a laundering signal, and an expert report that
quotes both is far harder to attack on cross-examination.

The engine is pure -- no Neo4j, no Postgres, no network. The caller normalises
whatever it has (graph rows, `transactions` rows, a provider response) into
`Transfer` and passes a list. That keeps the forensic maths reproducible and
lets the same code back an API route, a Celery job, and a court exhibit.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

from .types import Transfer, normalize_address

logger = structlog.get_logger(__name__)

MODEL_HAIRCUT = "haircut"
MODEL_FIFO = "fifo"

# USD amounts are floats, so repeated debit/credit leaves sub-nano residue.
# Anything under this is treated as zero rather than allowed to accumulate
# into a phantom fraction of a cent that survives thousands of hops.
_EPSILON = 1e-9


@dataclass(frozen=True)
class TaintResult:
    """How much of what an address received is provably illicit."""

    address: str
    taint_ratio: float
    tainted_value_usd: float
    received_value_usd: float
    hops: int
    model: str


@dataclass
class _Lot:
    """One chronological parcel of value sitting in a FIFO wallet."""

    value_usd: float
    tainted_usd: float


@dataclass
class _Account:
    """Running ledger for one address.

    `received_*` is cumulative and never decreases -- it is the denominator of
    the reported ratio, because the forensic question is "of everything that
    ever landed here, how much was dirty", not "how much is dirty right now".
    `balance_*` is the live position that decides what an outgoing transfer
    carries. `hops` is the shortest tainted path found so far, so a wallet
    reached again by a shorter route is re-ranked rather than double counted.
    """

    received_usd: float = 0.0
    tainted_received_usd: float = 0.0
    balance_usd: float = 0.0
    tainted_balance_usd: float = 0.0
    hops: int | None = None
    lots: deque[_Lot] = field(default_factory=deque)


def _sort_key(transfer: Transfer) -> tuple[datetime, str, str, str, float]:
    """Total order over transfers.

    Timestamp alone is not a total order -- same-block transfers share a
    timestamp, and under FIFO the order of two same-second deposits changes
    the answer. Falling through to tx_hash and the endpoints makes the result
    reproducible, which is the whole point of an exhibit an opposing expert
    will try to re-run.
    """
    return (
        transfer.timestamp,
        transfer.tx_hash,
        transfer.from_address,
        transfer.to_address,
        transfer.value_usd,
    )


def _prepare(transfers: Sequence[Transfer]) -> list[Transfer]:
    """Drop non-movements and impose the deterministic order.

    Zero/negative legs are provider noise (failed calls, internal accounting
    rows, mispriced dust) and self-transfers move no money between parties --
    counting either would inflate the `received` denominator and silently
    dilute every downstream taint percentage.
    """
    movements = [t for t in transfers if t.value_usd > 0 and t.from_address != t.to_address]
    return sorted(movements, key=_sort_key)


def _seed(
    ledger: dict[str, _Account],
    sources: Mapping[str, float],
    *,
    track_lots: bool,
) -> None:
    """Place the stolen funds into their originating wallets at hop 0."""
    # Sorted so float accumulation is identical run to run.
    for raw_address, amount in sorted(sources.items()):
        if amount <= 0:
            continue
        address = normalize_address(raw_address)
        account = ledger.setdefault(address, _Account())
        account.received_usd += amount
        account.tainted_received_usd += amount
        account.balance_usd += amount
        account.tainted_balance_usd += amount
        account.hops = 0
        if track_lots:
            # The theft predates everything else we can see, so it is the
            # oldest lot -- under FIFO it is therefore the first to leave.
            account.lots.append(_Lot(value_usd=amount, tainted_usd=amount))


def _credit(
    account: _Account,
    value_usd: float,
    tainted_usd: float,
    sender_hops: int | None,
    *,
    track_lots: bool,
) -> None:
    account.received_usd += value_usd
    account.tainted_received_usd += tainted_usd
    account.balance_usd += value_usd
    account.tainted_balance_usd += tainted_usd
    if track_lots:
        account.lots.append(_Lot(value_usd=value_usd, tainted_usd=tainted_usd))
    if tainted_usd > _EPSILON and sender_hops is not None:
        hop = sender_hops + 1
        account.hops = hop if account.hops is None else min(account.hops, hop)


def _settle(account: _Account) -> None:
    """A wallet can never hold more taint than value.

    We routinely see only a slice of a wallet's history, so an address can
    appear to spend more than it was ever observed receiving. Clamping here
    stops that gap from manufacturing taint out of nothing.
    """
    account.balance_usd = max(0.0, account.balance_usd)
    account.tainted_balance_usd = max(0.0, min(account.tainted_balance_usd, account.balance_usd))


def _debit_haircut(account: _Account, value_usd: float) -> float:
    """Pro-rata: the leg carries the wallet's current taint percentage."""
    carried = 0.0
    if account.balance_usd > _EPSILON and account.tainted_balance_usd > _EPSILON:
        ratio = min(1.0, max(0.0, account.tainted_balance_usd / account.balance_usd))
        carried = min(ratio * value_usd, account.tainted_balance_usd)

    account.balance_usd -= value_usd
    account.tainted_balance_usd -= carried
    _settle(account)
    return carried


def _debit_fifo(account: _Account, value_usd: float) -> float:
    """Poison: consume the oldest lots and forward exactly their taint."""
    remaining = value_usd
    carried = 0.0

    while remaining > _EPSILON and account.lots:
        lot = account.lots[0]
        if lot.value_usd <= _EPSILON:
            account.lots.popleft()
            continue
        taken = min(lot.value_usd, remaining)
        share = min(lot.tainted_usd, lot.tainted_usd * (taken / lot.value_usd))
        carried += share
        lot.value_usd -= taken
        lot.tainted_usd = max(0.0, lot.tainted_usd - share)
        remaining -= taken
        if lot.value_usd <= _EPSILON:
            account.lots.popleft()

    # `remaining > 0` means the wallet spent value we never observed arriving;
    # that unseen portion is treated as clean rather than guessed at.
    account.balance_usd -= value_usd
    account.tainted_balance_usd -= carried
    _settle(account)
    return min(carried, value_usd)


def _build_results(
    ledger: Mapping[str, _Account],
    *,
    model: str,
    min_taint_usd: float,
) -> dict[str, TaintResult]:
    results: dict[str, TaintResult] = {}
    for address, account in sorted(ledger.items()):
        if account.hops is None:
            continue
        tainted = min(account.tainted_received_usd, account.received_usd)
        if tainted < min_taint_usd:
            continue
        ratio = tainted / account.received_usd if account.received_usd > _EPSILON else 0.0
        results[address] = TaintResult(
            address=address,
            taint_ratio=min(1.0, max(0.0, ratio)),
            tainted_value_usd=tainted,
            received_value_usd=account.received_usd,
            hops=account.hops,
            model=model,
        )
    return results


def _propagate(
    transfers: Sequence[Transfer],
    sources: Mapping[str, float],
    *,
    model: str,
    max_hops: int,
    min_taint_usd: float,
) -> dict[str, TaintResult]:
    if not transfers or not sources:
        return {}

    track_lots = model == MODEL_FIFO
    ledger: dict[str, _Account] = {}
    _seed(ledger, sources, track_lots=track_lots)
    if not ledger:
        return {}

    debit = _debit_fifo if track_lots else _debit_haircut

    # One forward pass over a finite, time-ordered list. A cycle A->B->C->A is
    # therefore traversed exactly as often as it actually occurred on chain:
    # there is no fixpoint iteration to diverge, and taint can only be split
    # or dropped at each hop, never created.
    for transfer in _prepare(transfers):
        sender = ledger.setdefault(transfer.from_address, _Account())
        receiver = ledger.setdefault(transfer.to_address, _Account())

        # The sender is debited even past the hop horizon -- otherwise taint
        # would pile up in a wallet that demonstrably spent it away and leak
        # back out later through a shorter path.
        carried = debit(sender, transfer.value_usd)
        within_horizon = sender.hops is not None and sender.hops < max_hops
        forwarded = carried if within_horizon else 0.0

        _credit(
            receiver,
            transfer.value_usd,
            forwarded,
            sender.hops,
            track_lots=track_lots,
        )

    results = _build_results(ledger, model=model, min_taint_usd=min_taint_usd)
    logger.debug(
        "taint_propagated",
        model=model,
        transfers=len(transfers),
        sources=len(sources),
        max_hops=max_hops,
        tainted_addresses=len(results),
    )
    return results


def propagate_haircut(
    transfers: Sequence[Transfer],
    sources: Mapping[str, float],
    *,
    max_hops: int = 6,
    min_taint_usd: float = 1.0,
) -> dict[str, TaintResult]:
    """Pro-rata taint: every outgoing dollar carries the wallet's taint share."""
    return _propagate(
        transfers,
        sources,
        model=MODEL_HAIRCUT,
        max_hops=max_hops,
        min_taint_usd=min_taint_usd,
    )


def propagate_fifo(
    transfers: Sequence[Transfer],
    sources: Mapping[str, float],
    *,
    max_hops: int = 6,
    min_taint_usd: float = 1.0,
) -> dict[str, TaintResult]:
    """First-in-first-out taint: the oldest lots leave first, taint and all."""
    return _propagate(
        transfers,
        sources,
        model=MODEL_FIFO,
        max_hops=max_hops,
        min_taint_usd=min_taint_usd,
    )


def taint_summary(
    results: Mapping[str, TaintResult],
    *,
    top_n: int = 20,
) -> list[dict[str, Any]]:
    """Rank tainted addresses by recoverable dollars, for the API layer.

    Ordered by absolute tainted USD rather than percentage: a deposit wallet
    holding $4m at 40% taint is the freeze request worth filing, while a
    100%-tainted $12 dust hop is not. Address is the tie-break so two runs
    over the same evidence produce byte-identical output.
    """
    ranked = sorted(results.values(), key=lambda r: (-r.tainted_value_usd, r.address))
    return [
        {
            "address": result.address,
            "taint_ratio": round(result.taint_ratio, 6),
            "taint_percent": round(result.taint_ratio * 100, 2),
            "tainted_value_usd": round(result.tainted_value_usd, 2),
            "received_value_usd": round(result.received_value_usd, 2),
            "hops": result.hops,
            "model": result.model,
        }
        for result in ranked[: max(0, top_n)]
    ]


__all__ = [
    "MODEL_FIFO",
    "MODEL_HAIRCUT",
    "TaintResult",
    "propagate_fifo",
    "propagate_haircut",
    "taint_summary",
]
