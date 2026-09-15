"""Tests for the temporal laundering-motif engine.

Every case builds `Transfer` records directly, so these run with no Postgres,
no Neo4j and no network. The graphs are small and hand-shaped: each one is the
textbook form of a motif, or the same form broken in exactly one way, so a
failure points at the constraint that stopped working.
"""

import random
import time
from datetime import UTC, datetime, timedelta

from src.analytics.motif_engine import (
    MotifMatch,
    detect_cycles,
    detect_fan_out_fan_in,
    detect_motifs,
    detect_peel_chain,
)
from src.analytics.types import Transfer

BASE = datetime(2025, 3, 1, 9, 0, tzinfo=UTC)


def _transfer(
    sender: str,
    recipient: str,
    value: float,
    offset_seconds: float,
    tag: str = "",
) -> Transfer:
    """One hop `offset_seconds` after the fixture epoch."""
    label = tag or f"{sender}-{recipient}-{int(offset_seconds)}"
    return Transfer(
        tx_hash=f"0x{label}",
        from_address=sender,
        to_address=recipient,
        value_usd=value,
        timestamp=BASE + timedelta(seconds=offset_seconds),
    )


def _smurf_fan(
    mule_count: int = 4,
    fan_in_offset: float = 600.0,
    slice_usd: float = 25_000.0,
) -> list[Transfer]:
    """Source splits across mules, every mule forwards into one deposit."""
    transfers: list[Transfer] = []
    for index in range(mule_count):
        mule = f"0xmule{index}"
        transfers.append(_transfer("0xsource", mule, slice_usd, 60 * index))
        transfers.append(_transfer(mule, "0xdeposit", slice_usd * 0.99, fan_in_offset + 60 * index))
    return transfers


def _peel_chain(links: int = 4, peel_fraction: float = 0.1) -> list[Transfer]:
    """A corridor where each hop peels `peel_fraction` to a fresh VASP."""
    transfers = [_transfer("0xvictim", "0xhop0", 1_000_000.0, 0, tag="entry")]
    held = 1_000_000.0
    for index in range(links):
        peeled = held * peel_fraction
        forwarded = held - peeled
        transfers.append(_transfer(f"0xhop{index}", f"0xvasp{index}", peeled, 3600 * index + 100))
        transfers.append(
            _transfer(f"0xhop{index}", f"0xhop{index + 1}", forwarded, 3600 * index + 200)
        )
        held = forwarded
    return transfers


def test_classic_smurfing_fan_is_detected():
    """Source -> 4 mules -> one deposit inside the window is one match."""
    matches = detect_fan_out_fan_in(_smurf_fan())

    assert len(matches) == 1
    match = matches[0]
    assert match.motif == "fan_out_fan_in"
    assert match.addresses == (
        "0xsource",
        "0xmule0",
        "0xmule1",
        "0xmule2",
        "0xmule3",
        "0xdeposit",
    )
    assert len(match.tx_hashes) == 8
    assert match.value_usd == 100_000.0
    assert 0.0 < match.confidence <= 1.0
    assert match.window_seconds <= 1800
    assert match.detail["mule_count"] == 4
    assert match.detail["sink"] == "0xdeposit"


def test_fan_in_a_week_later_is_not_a_match():
    """Same topology, but Delta t between the bursts blows the window."""
    a_week = 7 * 24 * 3600
    assert detect_fan_out_fan_in(_smurf_fan(fan_in_offset=a_week)) == []


def test_fan_below_the_mule_floor_is_not_a_match():
    """Two mules is a split payment, not a smurf."""
    assert detect_fan_out_fan_in(_smurf_fan(mule_count=2)) == []
    assert len(detect_fan_out_fan_in(_smurf_fan(mule_count=2), min_mules=2)) == 1


def test_mule_that_forwards_a_wildly_different_amount_is_dropped():
    """A topological coincidence is not a leg of the fan."""
    transfers = _smurf_fan(mule_count=4)
    # Mule 3 forwards 40x what it received -- unrelated funds.
    transfers = [t for t in transfers if t.from_address != "0xmule3"]
    transfers.append(_transfer("0xmule3", "0xdeposit", 1_000_000.0, 700))

    matches = detect_fan_out_fan_in(transfers)
    assert len(matches) == 1
    assert matches[0].detail["mules"] == ["0xmule0", "0xmule1", "0xmule2"]


def test_peel_chain_with_thin_peels_is_detected():
    """Four hops each shaving 10% to a VASP is one peel chain."""
    matches = detect_peel_chain(_peel_chain(links=4))

    assert len(matches) == 1
    match = matches[0]
    assert match.motif == "peel_chain"
    assert match.detail["links"] == 4
    assert match.detail["path"] == [
        "0xvictim",
        "0xhop0",
        "0xhop1",
        "0xhop2",
        "0xhop3",
        "0xhop4",
    ]
    assert match.detail["peel_addresses"] == ["0xvasp0", "0xvasp1", "0xvasp2", "0xvasp3"]
    assert match.value_usd == 1_000_000.0
    assert all(ratio <= 0.4 for ratio in match.detail["peel_ratios"])
    assert 0.0 < match.confidence <= 1.0


def test_chain_peeling_most_of_the_value_is_not_a_peel_chain():
    """Shaving 90% per hop is a fan-out corridor, not a peel."""
    assert detect_peel_chain(_peel_chain(links=4, peel_fraction=0.9)) == []


def test_short_peel_chain_is_below_the_length_floor():
    """Two peeling hops do not establish a corridor."""
    assert detect_peel_chain(_peel_chain(links=2)) == []
    assert len(detect_peel_chain(_peel_chain(links=2), min_length=2)) == 1


def test_cycle_is_detected_and_an_acyclic_path_is_not():
    """A -> B -> C -> A closes the loop; A -> B -> C -> D does not."""
    loop = [
        _transfer("0xa", "0xb", 50_000.0, 0),
        _transfer("0xb", "0xc", 49_000.0, 300),
        _transfer("0xc", "0xa", 48_000.0, 600),
    ]
    matches = detect_cycles(loop)
    assert len(matches) == 1
    assert matches[0].motif == "cycle"
    assert matches[0].addresses == ("0xa", "0xb", "0xc")
    assert matches[0].window_seconds == 600.0
    assert matches[0].value_usd == 48_000.0

    acyclic = loop[:2] + [_transfer("0xc", "0xd", 48_000.0, 600)]
    assert detect_cycles(acyclic) == []


def test_cycle_longer_than_the_bound_is_ignored():
    """An 8-hop ring is outside a max_length of 6."""
    ring = [f"0xr{index}" for index in range(8)]
    transfers = [
        _transfer(ring[index], ring[(index + 1) % len(ring)], 10_000.0, 300 * index)
        for index in range(len(ring))
    ]

    assert detect_cycles(transfers, max_length=6) == []
    assert len(detect_cycles(transfers, max_length=8)) == 1


def test_cycle_that_closes_after_the_window_is_ignored():
    """A ring that takes a year to close is not a wash trade."""
    slow = [
        _transfer("0xa", "0xb", 50_000.0, 0),
        _transfer("0xb", "0xc", 49_000.0, 300),
        _transfer("0xc", "0xa", 48_000.0, 400 * 86400),
    ]
    assert detect_cycles(slow) == []
    assert len(detect_cycles(slow, window_seconds=500 * 86400)) == 1


def test_detect_motifs_returns_every_kind_sorted_by_value():
    """One combined graph carrying all three motifs, ordered deterministically."""
    transfers = [
        *_smurf_fan(),
        *_peel_chain(links=4),
        _transfer("0xwash1", "0xwash2", 500_000.0, 10),
        _transfer("0xwash2", "0xwash3", 495_000.0, 20),
        _transfer("0xwash3", "0xwash1", 490_000.0, 30),
    ]

    matches = detect_motifs(transfers)

    assert {match.motif for match in matches} == {"fan_out_fan_in", "peel_chain", "cycle"}
    values = [match.value_usd for match in matches]
    assert values == sorted(values, reverse=True)
    assert all(isinstance(match, MotifMatch) for match in matches)
    # Deterministic: the same evidence must produce byte-identical findings.
    assert detect_motifs(transfers) == matches


def test_empty_and_worthless_input_returns_nothing():
    """No transfers, and transfers that moved no money, both find nothing."""
    assert detect_motifs([]) == []
    assert detect_fan_out_fan_in([]) == []
    assert detect_peel_chain([]) == []
    assert detect_cycles([]) == []

    noise = [_transfer("0xsource", f"0xmule{index}", 0.0, index) for index in range(5)] + [
        _transfer("0xloop", "0xloop", 10_000.0, 1)
    ]
    assert detect_motifs(noise) == []


def test_two_thousand_transfers_complete_quickly():
    """The caps must keep a case-sized graph interactive."""
    rng = random.Random(20250301)
    addresses = [f"0xw{index:04d}" for index in range(300)]
    transfers = []
    for index in range(2000):
        sender, recipient = rng.sample(addresses, 2)
        transfers.append(
            _transfer(sender, recipient, rng.uniform(100.0, 50_000.0), index * 30, tag=f"s{index}")
        )
    # Plant one unmistakable smurf fan so the run is not merely finding nothing.
    transfers.extend(_smurf_fan())

    started = time.perf_counter()
    matches = detect_motifs(transfers)
    elapsed = time.perf_counter() - started

    assert elapsed < 5.0, f"motif mining took {elapsed:.2f}s"
    assert any(
        match.motif == "fan_out_fan_in" and match.detail["sink"] == "0xdeposit" for match in matches
    )
