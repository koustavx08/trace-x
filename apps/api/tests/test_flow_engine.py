"""Tests for the flow-weighted path and max-flow / min-cut engine (spec 2.2).

The engine is pure, so these build `Transfer` records directly and touch no
database, Neo4j or provider -- they run anywhere pytest does.
"""

import json
import math
from datetime import UTC, datetime

import networkx as nx
import pytest

from src.analytics.flow_engine import (
    build_flow_graph,
    flow_weighted_path,
    max_flow_min_cut,
    value_weight,
)
from src.analytics.types import Transfer

_START = datetime(2024, 3, 1, 12, 0, tzinfo=UTC)


def _transfer(
    sender: str,
    recipient: str,
    value_usd: float,
    *,
    minute: int = 0,
    tx_hash: str | None = None,
) -> Transfer:
    return Transfer(
        tx_hash=tx_hash or f"0x{sender}{recipient}{minute}",
        from_address=sender,
        to_address=recipient,
        value_usd=value_usd,
        timestamp=_START.replace(minute=minute),
    )


def test_value_weight_falls_as_value_rises():
    """The whole point of the inverse-log weight: more money, cheaper edge."""
    weights = [value_weight(value) for value in (1.0, 10.0, 1_000.0, 1_000_000.0, 1e12)]
    assert weights == sorted(weights, reverse=True)
    assert all(first > second for first, second in zip(weights, weights[1:], strict=False))


@pytest.mark.parametrize("value", [0.0, -1.0, -1e9, 1e12, 1e-12, float("nan"), float("inf")])
def test_value_weight_is_always_finite_and_positive(value):
    """Provider data is dirty; a NaN weight would poison the entire search."""
    weight = value_weight(value)
    assert weight > 0.0
    assert math.isfinite(weight)


def test_dijkstra_takes_the_million_dollar_corridor_over_the_decoy_hop():
    """The spec's motivating case: one $10 hop vs two hops of $1,000,000."""
    transfers = [
        _transfer("0xSUSPECT", "0xEXCHANGE", 10.0, minute=1),
        _transfer("0xsuspect", "0xLAYER", 1_000_000.0, minute=2),
        _transfer("0xLAYER", "0xexchange", 1_000_000.0, minute=3),
    ]

    result = flow_weighted_path(transfers, "0xSUSPECT", "0xEXCHANGE")

    assert result is not None
    assert result.nodes == ("0xsuspect", "0xlayer", "0xexchange")
    assert result.hops == 2
    assert result.total_value_usd == pytest.approx(2_000_000.0)

    # A plain hop-count search -- what the graph layer did before -- would have
    # reported the decoy instead.
    graph = build_flow_graph(transfers)
    assert nx.shortest_path(graph, "0xsuspect", "0xexchange") == ["0xsuspect", "0xexchange"]


def test_parallel_transfers_aggregate_into_one_edge():
    """A smurfing run between one pair is a single corridor, not 3 thin ones."""
    transfers = [
        _transfer("0xA", "0xB", 5_000.0, minute=5, tx_hash="0xthird"),
        _transfer("0xA", "0xB", 5_000.0, minute=1, tx_hash="0xfirst"),
        _transfer("0xa", "0xb", 5_000.0, minute=3, tx_hash="0xsecond"),
    ]

    graph = build_flow_graph(transfers)
    edge = graph["0xa"]["0xb"]

    assert graph.number_of_edges() == 1
    assert edge["tx_count"] == 3
    assert edge["capacity_usd"] == pytest.approx(15_000.0)
    assert edge["value_usd"] == pytest.approx(15_000.0)
    assert edge["weight"] == pytest.approx(value_weight(15_000.0))
    # Ordered by time, so the hashes read as the sequence of hops they were.
    assert edge["tx_hashes"] == ("0xfirst", "0xsecond", "0xthird")
    assert edge["first_seen"] == _START.replace(minute=1)
    assert edge["last_seen"] == _START.replace(minute=5)


def test_max_flow_through_a_diamond_sums_both_branches():
    transfers = [
        _transfer("0xS", "0xA", 100.0),
        _transfer("0xA", "0xT", 100.0),
        _transfer("0xS", "0xB", 50.0),
        _transfer("0xB", "0xT", 50.0),
    ]

    result = max_flow_min_cut(transfers, "0xS", "0xT")

    assert result.max_flow_usd == pytest.approx(150.0)
    assert {path.nodes for path in result.flow_paths} == {
        ("0xs", "0xa", "0xt"),
        ("0xs", "0xb", "0xt"),
    }
    # Widest corridor first -- that is the one a report leads with.
    assert result.flow_paths[0].total_value_usd == pytest.approx(100.0)
    assert sum(path.total_value_usd for path in result.flow_paths) == pytest.approx(150.0)


def test_a_narrow_edge_caps_the_flow_and_is_the_freeze_target():
    """$1,000,000 either side of a $10,000 hop still only moves $10,000."""
    transfers = [
        _transfer("0xS", "0xA", 1_000_000.0),
        _transfer("0xA", "0xB", 10_000.0),
        _transfer("0xB", "0xT", 1_000_000.0),
    ]

    result = max_flow_min_cut(transfers, "0xS", "0xT")

    assert result.max_flow_usd == pytest.approx(10_000.0)
    assert result.min_cut_edges == (("0xa", "0xb"),)
    assert result.bottleneck_usd == pytest.approx(10_000.0)
    assert result.flow_paths[0].nodes == ("0xs", "0xa", "0xb", "0xt")
    assert result.flow_paths[0].edges[0]["flow_usd"] == pytest.approx(10_000.0)


def test_unknown_wallets_are_answered_not_raised():
    transfers = [_transfer("0xA", "0xB", 100.0)]

    assert flow_weighted_path(transfers, "0xGHOST", "0xB") is None
    assert flow_weighted_path(transfers, "0xA", "0xGHOST") is None
    # Present, but nothing flows between them.
    assert flow_weighted_path(transfers, "0xB", "0xA") is None

    zeroed = max_flow_min_cut(transfers, "0xA", "0xGHOST")
    assert zeroed.max_flow_usd == 0.0
    assert zeroed.min_cut_edges == ()
    assert zeroed.bottleneck_usd == 0.0
    assert zeroed.flow_paths == ()
    assert zeroed.source == "0xa"
    assert zeroed.target == "0xghost"


def test_max_hops_rejects_an_over_long_chain():
    chain = ["0xA", "0xB", "0xC", "0xD", "0xE"]
    transfers = [
        _transfer(sender, recipient, 1_000.0, minute=index)
        for index, (sender, recipient) in enumerate(zip(chain, chain[1:], strict=False))
    ]

    assert flow_weighted_path(transfers, "0xA", "0xE", max_hops=2) is None

    within = flow_weighted_path(transfers, "0xA", "0xE", max_hops=4)
    assert within is not None
    assert within.hops == 4


def test_empty_transfer_list_is_handled():
    assert build_flow_graph([]).number_of_nodes() == 0
    assert flow_weighted_path([], "0xA", "0xB") is None

    result = max_flow_min_cut([], "0xA", "0xB")
    assert result.max_flow_usd == 0.0
    assert result.flow_paths == ()


def test_self_loops_and_zero_value_transfers_are_dropped():
    transfers = [
        _transfer("0xA", "0xA", 5_000.0),
        _transfer("0xA", "0xB", 0.0),
        _transfer("0xA", "0xB", -10.0),
        _transfer("0xA", "0xB", 500.0, minute=4),
    ]

    graph = build_flow_graph(transfers)

    assert graph.number_of_edges() == 1
    assert graph["0xa"]["0xb"]["capacity_usd"] == pytest.approx(500.0)
    assert graph["0xa"]["0xb"]["tx_count"] == 1


def test_results_are_deterministic_regardless_of_input_order():
    """A re-run of the same case file must produce the same corridor."""
    transfers = [
        _transfer("0xS", "0xA", 100.0),
        _transfer("0xA", "0xT", 100.0),
        _transfer("0xS", "0xB", 100.0),
        _transfer("0xB", "0xT", 100.0),
    ]

    first = max_flow_min_cut(transfers, "0xS", "0xT")
    second = max_flow_min_cut(list(reversed(transfers)), "0xS", "0xT")

    assert first == second
    assert flow_weighted_path(transfers, "0xS", "0xT") == flow_weighted_path(
        list(reversed(transfers)), "0xS", "0xT"
    )


def test_path_edges_are_json_serialisable():
    """These descriptors go straight into API responses and evidence exports."""
    transfers = [_transfer("0xA", "0xB", 1_000.0), _transfer("0xB", "0xC", 900.0)]

    result = flow_weighted_path(transfers, "0xA", "0xC")

    assert result is not None
    encoded = json.loads(json.dumps(result.edges))
    assert encoded[0]["from_address"] == "0xa"
    assert encoded[0]["first_seen"].startswith("2024-03-01T12:00:00")
    assert encoded[0]["tx_hashes"] == [transfers[0].tx_hash]
