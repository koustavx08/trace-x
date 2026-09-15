"""Unit tests for the cross-chain bridge matcher and the 1930/I4C fiat correlator.

Pure in-memory fixtures: no database, no network, no event loop.
"""

from datetime import UTC, datetime, timedelta

from src.analytics.correlation_engine import (
    BridgeMatch,
    FiatCorrelation,
    correlate_fiat_to_chain,
    match_bridge_transfers,
)
from src.analytics.types import FiatPayment, Transfer

T0 = datetime(2025, 3, 11, 9, 0, 0, tzinfo=UTC)

BRIDGE = "0xBbbbBBbbbbBBbbBBbbBBbBbbBbBbbbBBbBBbBB01"
SUSPECT = "0xAaAaAAAaaaAAAAaaAAaaaaAaAAaAAAAaAaAaAa02"
LANDING = "0xCcCcCcCCccCCccCCCcCccCcCCCCcCCCCccCcCc03"


def _out(
    tx: str,
    *,
    value: float,
    at: datetime,
    chain: str = "ethereum",
    to: str = BRIDGE,
    frm: str = SUSPECT,
) -> Transfer:
    return Transfer(
        tx_hash=tx,
        from_address=frm,
        to_address=to,
        value_usd=value,
        timestamp=at,
        chain=chain,
        asset="USDT",
    )


def _in(
    tx: str,
    *,
    value: float,
    at: datetime,
    chain: str = "polygon",
    to: str = LANDING,
) -> Transfer:
    return Transfer(
        tx_hash=tx,
        from_address=BRIDGE,
        to_address=to,
        value_usd=value,
        timestamp=at,
        chain=chain,
        asset="USDT",
    )


def _pay(ref: str, *, inr: float, at: datetime) -> FiatPayment:
    return FiatPayment(
        reference_id=ref,
        payer_account="HDFC0001234567890",
        payee_account="SBIN0009876543210",
        amount_inr=inr,
        timestamp=at,
        rail="UPI",
    )


def _release(tx: str, *, usd: float, at: datetime) -> Transfer:
    return Transfer(
        tx_hash=tx,
        from_address=BRIDGE,
        to_address=LANDING,
        value_usd=usd,
        timestamp=at,
        chain="tron",
        asset="USDT",
    )


# --------------------------------------------------------------------------
# Bridge matcher (spec 3.6)
# --------------------------------------------------------------------------


def test_exact_bridge_hop_matches_with_high_confidence() -> None:
    source = _out("0xsrc", value=250_000.0, at=T0)
    destination = _in("0xdst", value=250_000.0, at=T0 + timedelta(minutes=5))

    matches = match_bridge_transfers([source], [destination])

    assert len(matches) == 1
    match = matches[0]
    assert isinstance(match, BridgeMatch)
    assert match.source_tx == "0xsrc"
    assert match.destination_tx == "0xdst"
    assert match.source_chain == "ethereum"
    assert match.destination_chain == "polygon"
    assert match.source_address == SUSPECT.lower()
    assert match.destination_address == LANDING.lower()
    assert match.value_delta_pct == 0.0
    assert match.elapsed_seconds == 300.0
    assert match.confidence > 0.9
    # No allowlist was supplied, so no bridge contract is asserted.
    assert match.bridge_address is None


def test_simultaneous_exact_hop_scores_full_confidence() -> None:
    matches = match_bridge_transfers(
        [_out("0xsrc", value=10_000.0, at=T0)],
        [_in("0xdst", value=10_000.0, at=T0)],
    )

    assert len(matches) == 1
    assert matches[0].confidence == 1.0


def test_fee_haircut_within_tolerance_still_matches() -> None:
    # 1.5% bridge/relayer fee -- the legs are close, never equal.
    matches = match_bridge_transfers(
        [_out("0xsrc", value=100_000.0, at=T0)],
        [_in("0xdst", value=98_500.0, at=T0 + timedelta(minutes=4))],
    )

    assert len(matches) == 1
    assert matches[0].value_delta_pct == 1.5


def test_large_value_gap_does_not_match() -> None:
    matches = match_bridge_transfers(
        [_out("0xsrc", value=100_000.0, at=T0)],
        [_in("0xdst", value=80_000.0, at=T0 + timedelta(minutes=4))],
    )

    assert matches == []


def test_inbound_leg_before_outbound_leg_never_matches() -> None:
    # Funds cannot be minted on chain B before they are locked on chain A.
    matches = match_bridge_transfers(
        [_out("0xsrc", value=50_000.0, at=T0)],
        [_in("0xdst", value=50_000.0, at=T0 - timedelta(minutes=5))],
    )

    assert matches == []


def test_outside_time_window_does_not_match() -> None:
    late = _in("0xdst", value=50_000.0, at=T0 + timedelta(seconds=3601))

    source = _out("0xsrc", value=50_000.0, at=T0)

    assert match_bridge_transfers([source], [late]) == []
    # The same pair is found once the window is widened.
    assert len(match_bridge_transfers([source], [late], window_seconds=7200)) == 1


def test_same_chain_legs_never_match() -> None:
    matches = match_bridge_transfers(
        [_out("0xsrc", value=50_000.0, at=T0, chain="ethereum")],
        [_in("0xdst", value=50_000.0, at=T0 + timedelta(minutes=2), chain="Ethereum")],
    )

    assert matches == []


def test_bridge_allowlist_excludes_non_bridge_counterparty() -> None:
    to_bridge = _out("0xbridged", value=50_000.0, at=T0, to=BRIDGE)
    to_random = _out(
        "0xrandom", value=50_000.0, at=T0, to="0xdeadBEEF00000000000000000000000000000001"
    )
    destinations = [
        _in("0xdst1", value=50_000.0, at=T0 + timedelta(minutes=2)),
        _in("0xdst2", value=50_000.0, at=T0 + timedelta(minutes=3)),
    ]

    matches = match_bridge_transfers(
        [to_bridge, to_random], destinations, bridge_addresses=[BRIDGE]
    )

    assert [m.source_tx for m in matches] == ["0xbridged"]
    # A confirmed allowlist hit names the contract, case-normalised.
    assert matches[0].bridge_address == BRIDGE.lower()


def test_one_outbound_leg_cannot_match_two_inbound_legs() -> None:
    source = _out("0xsrc", value=50_000.0, at=T0)
    destinations = [
        _in("0xdst_near", value=50_000.0, at=T0 + timedelta(minutes=2)),
        _in("0xdst_far", value=50_000.0, at=T0 + timedelta(minutes=30)),
    ]

    matches = match_bridge_transfers([source], destinations)

    assert len(matches) == 1


def test_greedy_bridge_assignment_prefers_the_closer_pair() -> None:
    source = _out("0xsrc", value=50_000.0, at=T0)
    destinations = [
        _in("0xdst_far", value=50_000.0, at=T0 + timedelta(minutes=30)),
        _in("0xdst_near", value=50_000.0, at=T0 + timedelta(minutes=2)),
    ]

    matches = match_bridge_transfers([source], destinations)

    assert [m.destination_tx for m in matches] == ["0xdst_near"]


def test_bridge_matches_are_returned_strongest_first() -> None:
    sources = [
        _out("0xsrc_weak", value=100_000.0, at=T0),
        _out("0xsrc_strong", value=40_000.0, at=T0),
    ]
    destinations = [
        # 1.8% haircut, 50 minutes later -- admissible but weak.
        _in("0xdst_weak", value=98_200.0, at=T0 + timedelta(minutes=50)),
        _in("0xdst_strong", value=40_000.0, at=T0 + timedelta(minutes=1)),
    ]

    matches = match_bridge_transfers(sources, destinations)

    assert [m.source_tx for m in matches] == ["0xsrc_strong", "0xsrc_weak"]
    assert matches[0].confidence > matches[1].confidence


def test_bridge_matcher_filters_malformed_rows_without_raising() -> None:
    rows_out = [
        _out("", value=50_000.0, at=T0),
        _out("0xzero", value=0.0, at=T0),
        _out("0xgood", value=50_000.0, at=T0),
    ]
    rows_in = [
        _in("0xbadvalue", value=-1.0, at=T0 + timedelta(minutes=1)),
        _in("0xgooddst", value=50_000.0, at=T0 + timedelta(minutes=1)),
    ]

    matches = match_bridge_transfers(rows_out, rows_in)

    assert [(m.source_tx, m.destination_tx) for m in matches] == [("0xgood", "0xgooddst")]


def test_bridge_matcher_returns_empty_for_empty_inputs() -> None:
    assert match_bridge_transfers([], []) == []
    assert match_bridge_transfers([_out("0xsrc", value=1.0, at=T0)], []) == []
    assert match_bridge_transfers([], [_in("0xdst", value=1.0, at=T0)]) == []


# --------------------------------------------------------------------------
# Fiat / escrow correlator (spec 3.4)
# --------------------------------------------------------------------------


def test_upi_payment_three_minutes_before_release_correlates() -> None:
    payment = _pay("UPI-2025-0001", inr=830_000.0, at=T0)
    release = _release("0xescrow", usd=10_000.0, at=T0 + timedelta(minutes=3))

    correlations = correlate_fiat_to_chain([payment], [release])

    assert len(correlations) == 1
    hit = correlations[0]
    assert isinstance(hit, FiatCorrelation)
    assert hit.payment_reference == "UPI-2025-0001"
    assert hit.chain_tx == "0xescrow"
    assert hit.crypto_address == LANDING.lower()
    assert hit.payer_account == "HDFC0001234567890"
    assert hit.payee_account == "SBIN0009876543210"
    assert hit.implied_rate == 83.0
    assert hit.elapsed_seconds == 180.0
    assert hit.confidence > 0.8


def test_release_before_payment_still_correlates_inside_the_window() -> None:
    # An OTC desk that fronts the crypto releases first: same pattern, and the
    # signed gap records the direction.
    payment = _pay("UPI-2025-0002", inr=830_000.0, at=T0)
    release = _release("0xfronted", usd=10_000.0, at=T0 - timedelta(minutes=2))

    correlations = correlate_fiat_to_chain([payment], [release])

    assert len(correlations) == 1
    assert correlations[0].elapsed_seconds == -120.0


def test_payment_forty_minutes_away_does_not_correlate() -> None:
    payment = _pay("UPI-2025-0003", inr=830_000.0, at=T0)
    release = _release("0xescrow", usd=10_000.0, at=T0 + timedelta(minutes=40))

    assert correlate_fiat_to_chain([payment], [release]) == []


def test_amount_mismatch_beyond_tolerance_does_not_correlate() -> None:
    # INR 9.13 lakh against a USD 10k release is a 10% gap at INR 83/USD.
    payment = _pay("UPI-2025-0004", inr=913_000.0, at=T0)
    release = _release("0xescrow", usd=10_000.0, at=T0 + timedelta(minutes=1))

    assert correlate_fiat_to_chain([payment], [release]) == []


def test_off_market_implied_rate_is_surfaced_not_hidden() -> None:
    # A 4% premium over the reference rate still lands inside tolerance, and
    # the inflated rate itself is the red flag worth reporting.
    payment = _pay("UPI-2025-0005", inr=863_200.0, at=T0)
    release = _release("0xescrow", usd=10_000.0, at=T0 + timedelta(minutes=1))

    correlations = correlate_fiat_to_chain([payment], [release])

    assert len(correlations) == 1
    assert correlations[0].implied_rate == 86.32


def test_greedy_fiat_assignment_picks_the_closer_pair() -> None:
    payment = _pay("UPI-2025-0006", inr=830_000.0, at=T0)
    releases = [
        _release("0xfar", usd=10_000.0, at=T0 + timedelta(minutes=9)),
        _release("0xnear", usd=10_000.0, at=T0 + timedelta(minutes=1)),
    ]

    correlations = correlate_fiat_to_chain([payment], releases)

    assert [c.chain_tx for c in correlations] == ["0xnear"]


def test_each_payment_and_release_is_consumed_at_most_once() -> None:
    payments = [
        _pay("UPI-A", inr=830_000.0, at=T0),
        _pay("UPI-B", inr=830_000.0, at=T0 + timedelta(minutes=8)),
    ]
    releases = [
        _release("0xrel_a", usd=10_000.0, at=T0 + timedelta(minutes=1)),
        _release("0xrel_b", usd=10_000.0, at=T0 + timedelta(minutes=9)),
    ]

    correlations = correlate_fiat_to_chain(payments, releases)

    assert len(correlations) == 2
    assert {c.payment_reference for c in correlations} == {"UPI-A", "UPI-B"}
    assert {c.chain_tx for c in correlations} == {"0xrel_a", "0xrel_b"}
    pairs = {(c.payment_reference, c.chain_tx) for c in correlations}
    assert pairs == {("UPI-A", "0xrel_a"), ("UPI-B", "0xrel_b")}


def test_custom_rate_changes_which_release_matches() -> None:
    payment = _pay("UPI-2025-0007", inr=900_000.0, at=T0)
    release = _release("0xescrow", usd=10_000.0, at=T0 + timedelta(minutes=1))

    assert correlate_fiat_to_chain([payment], [release]) == []
    assert len(correlate_fiat_to_chain([payment], [release], usd_inr_rate=90.0)) == 1


def test_fiat_correlator_filters_malformed_rows_without_raising() -> None:
    payments = [
        _pay("", inr=830_000.0, at=T0),
        _pay("UPI-ZERO", inr=0.0, at=T0),
        _pay("UPI-GOOD", inr=830_000.0, at=T0),
    ]
    releases = [
        _release("0xzero", usd=0.0, at=T0 + timedelta(minutes=1)),
        _release("0xgood", usd=10_000.0, at=T0 + timedelta(minutes=1)),
    ]

    correlations = correlate_fiat_to_chain(payments, releases)

    assert [(c.payment_reference, c.chain_tx) for c in correlations] == [("UPI-GOOD", "0xgood")]


def test_fiat_correlator_returns_empty_for_empty_inputs() -> None:
    assert correlate_fiat_to_chain([], []) == []
    assert correlate_fiat_to_chain([_pay("UPI-X", inr=1000.0, at=T0)], []) == []
    assert correlate_fiat_to_chain([], [_release("0xrel", usd=10.0, at=T0)]) == []
