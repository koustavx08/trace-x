"""Taint engine tests -- pure arithmetic, no DB and no network.

Each case is a laundering pattern an investigator actually meets, not a
synthetic graph: the blueprint's worked example, a smurfing fan-out, the
clean-then-dirty deposit ordering that separates the two models, a wash
cycle, and a hop horizon.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.analytics.taint_engine import (
    TaintResult,
    propagate_fifo,
    propagate_haircut,
    taint_summary,
)
from src.analytics.types import Transfer

T0 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)


def _addr(tag: str) -> str:
    """A syntactically plausible EVM address, so normalisation is exercised."""
    return "0x" + tag.lower().rjust(40, "0")


def _transfer(
    sender: str,
    receiver: str,
    value_usd: float,
    minute: int,
    tx_hash: str | None = None,
) -> Transfer:
    return Transfer(
        tx_hash=tx_hash or f"0xtx{minute:04d}{sender[-4:]}{receiver[-4:]}",
        from_address=sender,
        to_address=receiver,
        value_usd=value_usd,
        timestamp=T0 + timedelta(minutes=minute),
    )


A = _addr("a")
B = _addr("b")
C = _addr("c")
D = _addr("d")
E = _addr("e")
CLEAN = _addr("c1ea4")


def test_blueprint_worked_example_splits_taint_pro_rata() -> None:
    """Blueprint 2.1: $100k balance, $75k illicit, three legs each 75% dirty."""
    transfers = [
        _transfer(CLEAN, A, 25_000, minute=0),
        _transfer(A, B, 30_000, minute=1),
        _transfer(A, C, 50_000, minute=2),
        _transfer(A, D, 20_000, minute=3),
    ]

    results = propagate_haircut(transfers, {A: 75_000})

    assert results[B].tainted_value_usd == pytest.approx(22_500)
    assert results[C].tainted_value_usd == pytest.approx(37_500)
    assert results[D].tainted_value_usd == pytest.approx(15_000)
    for address in (B, C, D):
        assert results[address].taint_ratio == pytest.approx(0.75)
        assert results[address].hops == 1
        assert results[address].model == "haircut"

    # The origin itself stays at hop 0 and reports the full seeded theft.
    assert results[A].hops == 0
    assert results[A].tainted_value_usd == pytest.approx(75_000)


@pytest.mark.parametrize("propagate", [propagate_haircut, propagate_fifo])
def test_smurfing_fan_out_conserves_total_taint(propagate) -> None:
    """Splitting stolen funds across mules must not dilute the total claim."""
    mules = [_addr(f"4u1e{i:02d}") for i in range(20)]
    transfers = [_transfer(A, mule, 5_000, minute=i + 1) for i, mule in enumerate(mules)]

    results = propagate(transfers, {A: 100_000})

    recovered = sum(results[mule].tainted_value_usd for mule in mules)
    assert recovered == pytest.approx(100_000)
    for mule in mules:
        assert results[mule].taint_ratio == pytest.approx(1.0)
        assert results[mule].hops == 1


def test_haircut_and_fifo_diverge_on_clean_then_dirty_ordering() -> None:
    """A launderer who pre-loads clean funds beats FIFO but not the haircut."""
    transfers = [
        _transfer(CLEAN, B, 100_000, minute=1),  # clean liquidity parked first
        _transfer(A, B, 100_000, minute=2),  # then the stolen funds land
        _transfer(B, E, 100_000, minute=3),  # forward exactly the clean amount
    ]
    sources = {A: 100_000}

    haircut = propagate_haircut(transfers, sources)
    fifo = propagate_fifo(transfers, sources)

    # Pro-rata: B is 50% dirty, so half of the onward leg is dirty too.
    assert haircut[B].taint_ratio == pytest.approx(0.5)
    assert haircut[E].tainted_value_usd == pytest.approx(50_000)

    # FIFO: the oldest lot was clean, so nothing dirty reaches E at all.
    assert fifo[B].taint_ratio == pytest.approx(0.5)
    assert E not in fifo

    fifo_reaching_e = fifo[E].tainted_value_usd if E in fifo else 0.0
    assert haircut[E].tainted_value_usd > fifo_reaching_e


@pytest.mark.parametrize("propagate", [propagate_haircut, propagate_fifo])
def test_wash_cycle_terminates_and_stays_bounded(propagate) -> None:
    """A -> B -> C -> A twice round must not loop forever or breed taint."""
    transfers = []
    minute = 1
    for _lap in range(2):
        for sender, receiver in ((A, B), (B, C), (C, A)):
            transfers.append(_transfer(sender, receiver, 100_000, minute=minute))
            minute += 1

    results = propagate(transfers, {A: 100_000})

    assert set(results) == {A, B, C}
    for result in results.values():
        assert 0.0 <= result.taint_ratio <= 1.0
        # Taint can be split or lost around the loop, never created.
        assert result.tainted_value_usd <= result.received_value_usd + 1e-6
        assert result.hops <= 2
    assert results[A].hops == 0


@pytest.mark.parametrize("propagate", [propagate_haircut, propagate_fifo])
def test_max_hops_stops_propagation(propagate) -> None:
    """Past the horizon the funds still move, but carry no taint with them."""
    transfers = [
        _transfer(A, B, 10_000, minute=1),
        _transfer(B, C, 10_000, minute=2),
        _transfer(C, D, 10_000, minute=3),
        _transfer(D, E, 10_000, minute=4),
    ]

    results = propagate(transfers, {A: 10_000}, max_hops=2)

    assert set(results) == {A, B, C}
    assert results[C].hops == 2
    assert D not in results
    assert E not in results

    # The same graph with headroom reaches the end of the chain.
    deep = propagate(transfers, {A: 10_000}, max_hops=6)
    assert deep[E].hops == 4
    assert deep[E].tainted_value_usd == pytest.approx(10_000)


@pytest.mark.parametrize("propagate", [propagate_haircut, propagate_fifo])
def test_clean_funds_never_acquire_taint(propagate) -> None:
    """An unrelated payment corridor must stay out of the report entirely."""
    transfers = [
        _transfer(A, B, 50_000, minute=1),
        _transfer(CLEAN, D, 80_000, minute=2),
        _transfer(D, E, 80_000, minute=3),
    ]

    results = propagate(transfers, {A: 50_000})

    assert set(results) == {A, B}
    assert CLEAN not in results
    assert D not in results
    assert E not in results


@pytest.mark.parametrize("propagate", [propagate_haircut, propagate_fifo])
def test_empty_inputs_return_no_results(propagate) -> None:
    assert propagate([], {A: 100_000}) == {}
    assert propagate([_transfer(A, B, 1_000, minute=1)], {}) == {}
    assert propagate([], {}) == {}
    assert propagate([_transfer(A, B, 1_000, minute=1)], {A: 0.0}) == {}

    # Zero-value noise legs move nothing, so only the seeded origin is reported.
    noise_only = propagate([_transfer(A, B, 0.0, minute=1)], {A: 100_000})
    assert set(noise_only) == {A}


def test_taint_summary_orders_by_dollars_and_caps_at_top_n() -> None:
    results = {
        _addr(f"5{i:03d}"): TaintResult(
            address=_addr(f"5{i:03d}"),
            taint_ratio=0.5,
            tainted_value_usd=float(i * 1_000),
            received_value_usd=float(i * 2_000),
            hops=2,
            model="haircut",
        )
        for i in range(1, 11)
    }

    summary = taint_summary(results, top_n=3)

    assert len(summary) == 3
    assert [row["tainted_value_usd"] for row in summary] == [10_000.0, 9_000.0, 8_000.0]
    assert summary[0]["address"] == _addr("5010")
    assert summary[0]["taint_percent"] == 50.0
    assert summary[0]["hops"] == 2
    assert summary[0]["model"] == "haircut"
    # Whole ranking when top_n exceeds the result count, still descending.
    full = taint_summary(results, top_n=100)
    assert len(full) == 10
    values = [row["tainted_value_usd"] for row in full]
    assert values == sorted(values, reverse=True)


def test_results_are_deterministic_regardless_of_input_order() -> None:
    """Two analysts re-running the same evidence must get the same exhibit."""
    transfers = [
        _transfer(A, B, 40_000, minute=1),
        _transfer(CLEAN, B, 60_000, minute=1),  # same timestamp, tie-broken by hash
        _transfer(B, C, 50_000, minute=2),
        _transfer(B, D, 50_000, minute=2),
    ]
    sources = {A: 40_000}

    forward = propagate_fifo(transfers, sources)
    reversed_order = propagate_fifo(list(reversed(transfers)), sources)

    assert taint_summary(forward) == taint_summary(reversed_order)
    assert list(forward) == list(reversed_order)


def test_min_taint_usd_drops_dust_results() -> None:
    """Sub-threshold hops are noise, not freeze requests."""
    transfers = [
        _transfer(A, B, 10_000, minute=1),
        _transfer(B, C, 2.0, minute=2),  # peels off $2, of which all is dirty
    ]

    kept = propagate_haircut(transfers, {A: 10_000}, min_taint_usd=1.0)
    dropped = propagate_haircut(transfers, {A: 10_000}, min_taint_usd=100.0)

    assert C in kept
    assert kept[C].tainted_value_usd == pytest.approx(2.0)
    assert C not in dropped
    assert B in dropped
