"""Correlation matchers that stitch a broken laundering trail back together.

Two distinct places where a cash-out chain stops being a single connected
graph are handled here, both from the algorithm spec:

* **Cross-chain bridges (spec 3.6).** The trail literally ends when funds are
  locked on chain A: they reappear as a mint on chain B under a different
  transaction hash, often to a different address. `match_bridge_transfers`
  re-links the deposit/lock leg to the mint/unlock leg.
* **P2P / OTC escrow (spec 3.4).** The trail leaves the chain entirely when a
  victim pays INR over UPI/IMPS into a mule account and a desk releases USDT
  in return. `correlate_fiat_to_chain` ties a 1930 / I4C complaint record to
  the on-chain escrow release it paid for.

Both are pure functions over the shared `Transfer` / `FiatPayment` records --
no database, no network -- so an investigator can replay them against evidence
exported from a case file and get an identical result, which is what makes the
output defensible in court.

Neither matcher asserts a link: it proposes one with a confidence, and the
investigator corroborates it with KYC or exchange records.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

import structlog

from .types import FiatPayment, Transfer, normalize_address

logger = structlog.get_logger(__name__)

# Confidence weighting. Value agreement outranks timing because any busy chain
# produces hundreds of transfers inside a given hour, but very few of them
# match a specific amount to within a couple of percent -- the amount is the
# discriminating evidence and the clock only corroborates it. Both terms decay
# linearly to zero at the edge of their tolerance, so confidence reaches 1.0
# only for a simultaneous, exact-value pair and degrades smoothly from there.
_TIME_WEIGHT = 0.4
_VALUE_WEIGHT = 0.6

_T = TypeVar("_T")


@dataclass(frozen=True)
class BridgeMatch:
    """A proposed deposit-leg / mint-leg pairing across two chains."""

    source_chain: str
    source_tx: str
    source_address: str
    destination_chain: str
    destination_tx: str
    destination_address: str
    value_usd: float
    value_delta_pct: float
    elapsed_seconds: float
    confidence: float
    bridge_address: str | None


@dataclass(frozen=True)
class FiatCorrelation:
    """A proposed bank-rail payment / on-chain escrow release pairing."""

    payment_reference: str
    payer_account: str
    payee_account: str
    chain_tx: str
    crypto_address: str
    amount_inr: float
    value_usd: float
    implied_rate: float
    elapsed_seconds: float
    confidence: float


@dataclass(frozen=True)
class _Candidate(Generic[_T]):
    """One scored pairing, plus what is needed to resolve it deterministically."""

    score: float
    tie_key: tuple[str, str]
    left: int
    right: int
    payload: _T


def _is_finite_positive(value: float) -> bool:
    """Zero, negative and NaN/inf amounts are corrupt rows, not evidence."""
    return isinstance(value, int | float) and math.isfinite(value) and value > 0


def _is_usable_transfer(transfer: Transfer) -> bool:
    """Drop rows that cannot carry a citation: no hash, no chain, no value."""
    return (
        bool(transfer.tx_hash and transfer.tx_hash.strip())
        and bool(transfer.chain and transfer.chain.strip())
        and _is_finite_positive(transfer.value_usd)
    )


def _is_usable_payment(payment: FiatPayment) -> bool:
    return bool(payment.reference_id and payment.reference_id.strip()) and _is_finite_positive(
        payment.amount_inr
    )


def _proximity(deviation: float, limit: float) -> float:
    """Linear closeness score: 1.0 at zero deviation, 0.0 at the limit."""
    if limit <= 0:
        # A zero tolerance means "exact or nothing" rather than a crash.
        return 1.0 if deviation <= 0 else 0.0
    return max(0.0, 1.0 - deviation / limit)


def _confidence(
    elapsed_seconds: float,
    window_seconds: float,
    deviation_pct: float,
    tolerance_pct: float,
) -> float:
    score = _TIME_WEIGHT * _proximity(abs(elapsed_seconds), window_seconds) + (
        _VALUE_WEIGHT * _proximity(deviation_pct, tolerance_pct)
    )
    return round(min(1.0, max(0.0, score)), 4)


def _greedy_assign(candidates: list[_Candidate[_T]]) -> list[_T]:
    """Best-first assignment in which each leg is consumed at most once.

    A globally optimal assignment (Hungarian) would also be defensible, but
    greedy is what an analyst can explain on the stand -- "the strongest
    pairing was taken first, then the strongest of what remained" -- and it
    still guarantees one deposit is never claimed by two mints. Ties break on
    the transaction hashes / reference ids so two runs over the same evidence
    produce the same report.
    """
    candidates.sort(key=lambda c: (-c.score, c.tie_key))
    used_left: set[int] = set()
    used_right: set[int] = set()
    chosen: list[_T] = []
    for candidate in candidates:
        if candidate.left in used_left or candidate.right in used_right:
            continue
        used_left.add(candidate.left)
        used_right.add(candidate.right)
        chosen.append(candidate.payload)
    return chosen


def match_bridge_transfers(
    outbound: Sequence[Transfer],
    inbound: Sequence[Transfer],
    *,
    window_seconds: int = 3600,
    value_tolerance_pct: float = 2.0,
    bridge_addresses: Collection[str] | None = None,
) -> list[BridgeMatch]:
    """Pair a lock/deposit leg on one chain with its mint/unlock leg on another.

    `outbound` holds the legs that enter the bridge, `inbound` the legs that
    leave it on the far side. A pairing is admissible only when the mint lands
    after the deposit and inside `window_seconds`, the USD-normalised values
    agree within `value_tolerance_pct` (bridge and relayer fees make them
    close, never equal), the two legs sit on different chains, and -- when an
    allowlist is supplied -- the deposit's counterparty is a known bridge
    contract.

    Results are returned strongest-first.
    """
    if window_seconds <= 0:
        return []

    known_bridges: set[str] | None = None
    if bridge_addresses is not None:
        known_bridges = {
            normalize_address(address)
            for address in bridge_addresses
            if address and address.strip()
        }

    sources = [t for t in outbound if _is_usable_transfer(t)]
    destinations = [t for t in inbound if _is_usable_transfer(t)]
    if not sources or not destinations:
        return []

    candidates: list[_Candidate[BridgeMatch]] = []
    for i, source in enumerate(sources):
        # The deposit leg's counterparty IS the bridge contract; anything else
        # is an ordinary transfer that merely happens to look like a hop.
        if known_bridges is not None and source.to_address not in known_bridges:
            continue
        for j, destination in enumerate(destinations):
            # A hop that lands on the chain it started from is not a bridge.
            if source.chain.strip().lower() == destination.chain.strip().lower():
                continue
            elapsed = (destination.timestamp - source.timestamp).total_seconds()
            if elapsed < 0 or elapsed > window_seconds:
                continue
            # Fees come out of the deposit, so the deposit is the baseline.
            delta_pct = abs(destination.value_usd - source.value_usd) / source.value_usd * 100.0
            if delta_pct > value_tolerance_pct:
                continue

            match = BridgeMatch(
                source_chain=source.chain,
                source_tx=source.tx_hash,
                source_address=source.from_address,
                destination_chain=destination.chain,
                destination_tx=destination.tx_hash,
                destination_address=destination.to_address,
                value_usd=source.value_usd,
                value_delta_pct=round(delta_pct, 4),
                elapsed_seconds=elapsed,
                confidence=_confidence(elapsed, window_seconds, delta_pct, value_tolerance_pct),
                # Named only when an allowlist confirmed it: otherwise the
                # counterparty is an unverified guess and must not be reported
                # as an identified bridge contract.
                bridge_address=source.to_address if known_bridges is not None else None,
            )
            candidates.append(
                _Candidate(
                    score=match.confidence,
                    tie_key=(source.tx_hash, destination.tx_hash),
                    left=i,
                    right=j,
                    payload=match,
                )
            )

    matches = _greedy_assign(candidates)
    logger.debug(
        "bridge_matching_complete",
        outbound_legs=len(sources),
        inbound_legs=len(destinations),
        candidates=len(candidates),
        matches=len(matches),
        window_seconds=window_seconds,
    )
    return matches


def correlate_fiat_to_chain(
    payments: Sequence[FiatPayment],
    releases: Sequence[Transfer],
    *,
    window_seconds: int = 600,
    usd_inr_rate: float = 83.0,
    amount_tolerance_pct: float = 5.0,
) -> list[FiatCorrelation]:
    """Tie a victim's UPI/IMPS payment to the USDT escrow release it paid for.

    The window is two-sided (the spec's +/- 10 minutes): a P2P desk usually
    releases escrow just after the fiat lands, but an OTC desk fronting the
    crypto releases first and collects the transfer seconds later, and both
    are the same laundering pattern.

    `implied_rate` is deliberately reported rather than folded away. A trade
    struck far off the market rate is itself a red flag -- an inflated rate is
    how a mule gets paid for the use of the account -- so the number goes in
    front of the investigator instead of disappearing into a score.

    Results are returned strongest-first.
    """
    if window_seconds <= 0 or not _is_finite_positive(usd_inr_rate):
        return []

    usable_payments = [p for p in payments if _is_usable_payment(p)]
    usable_releases = [r for r in releases if _is_usable_transfer(r)]
    if not usable_payments or not usable_releases:
        return []

    candidates: list[_Candidate[FiatCorrelation]] = []
    for i, payment in enumerate(usable_payments):
        for j, release in enumerate(usable_releases):
            # Signed: positive means the release followed the payment (the
            # normal escrow direction), negative means the desk fronted it.
            gap = (release.timestamp - payment.timestamp).total_seconds()
            if abs(gap) > window_seconds:
                continue
            expected_inr = release.value_usd * usd_inr_rate
            delta_pct = abs(payment.amount_inr - expected_inr) / expected_inr * 100.0
            if delta_pct > amount_tolerance_pct:
                continue

            correlation = FiatCorrelation(
                payment_reference=payment.reference_id,
                payer_account=payment.payer_account,
                payee_account=payment.payee_account,
                chain_tx=release.tx_hash,
                crypto_address=release.to_address,
                amount_inr=payment.amount_inr,
                value_usd=release.value_usd,
                implied_rate=round(payment.amount_inr / release.value_usd, 4),
                elapsed_seconds=gap,
                confidence=_confidence(gap, window_seconds, delta_pct, amount_tolerance_pct),
            )
            candidates.append(
                _Candidate(
                    score=correlation.confidence,
                    tie_key=(payment.reference_id, release.tx_hash),
                    left=i,
                    right=j,
                    payload=correlation,
                )
            )

    correlations = _greedy_assign(candidates)
    logger.debug(
        "fiat_correlation_complete",
        payments=len(usable_payments),
        releases=len(usable_releases),
        candidates=len(candidates),
        correlations=len(correlations),
        window_seconds=window_seconds,
        usd_inr_rate=usd_inr_rate,
    )
    return correlations


__all__ = [
    "BridgeMatch",
    "FiatCorrelation",
    "correlate_fiat_to_chain",
    "match_bridge_transfers",
]
