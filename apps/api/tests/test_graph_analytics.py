"""Tests for the in-process graph analytics.

These cover the algorithms that replaced the Neo4j GDS procedure calls. They
build graphs directly and need no database, so they run in CI without a Neo4j
service container.
"""

import networkx as nx
import pytest

from src.graph.analytics import _pagerank, detect_communities, rank_by_centrality


def _chain_graph() -> tuple[nx.DiGraph, dict[str, dict]]:
    """A peel chain: a -> b -> c -> d, with a side payment into c."""
    graph = nx.DiGraph()
    edges = [("a", "b", 100.0), ("b", "c", 90.0), ("c", "d", 80.0), ("e", "c", 10.0)]
    for source, target, value in edges:
        graph.add_edge(source, target, value_usd=value, tx_count=1)
    attributes = {
        node: {"address": node, "label": f"wallet {node}", "risk_score": 10.0} for node in graph
    }
    return graph, attributes


def test_pagerank_sums_to_one():
    """Rank is conserved -- the dangling-node handling is what makes this hold."""
    graph, _ = _chain_graph()
    scores = _pagerank(graph)
    assert pytest.approx(sum(scores.values()), abs=1e-9) == 1.0


def test_pagerank_ranks_the_sink_highest():
    """`d` is the end of the chain, so every path drains into it."""
    graph, attributes = _chain_graph()
    ranked = rank_by_centrality(graph, attributes, "pagerank", top_n=10)
    assert ranked[0]["address"] == "d"
    assert ranked[0]["score"] > ranked[-1]["score"]


def test_pagerank_is_deterministic():
    graph, attributes = _chain_graph()
    first = rank_by_centrality(graph, attributes, "pagerank", top_n=10)
    second = rank_by_centrality(graph, attributes, "pagerank", top_n=10)
    assert first == second


def test_pagerank_handles_a_graph_with_no_usd_values():
    """Wallets whose transfers carry no valuation must not be treated as sinks."""
    graph = nx.DiGraph()
    graph.add_edge("a", "b", value_usd=0.0, tx_count=1)
    graph.add_edge("b", "a", value_usd=0.0, tx_count=1)
    scores = _pagerank(graph)
    assert pytest.approx(sum(scores.values()), abs=1e-9) == 1.0
    assert pytest.approx(scores["a"], abs=1e-9) == scores["b"]


def test_isolated_wallets_are_ranked_not_dropped():
    graph, attributes = _chain_graph()
    graph.add_node("lonely")
    attributes["lonely"] = {"address": "lonely", "label": "no transfers", "risk_score": 0.0}
    ranked = rank_by_centrality(graph, attributes, "pagerank", top_n=10)
    assert "lonely" in {row["address"] for row in ranked}


def test_centrality_carries_wallet_labels():
    graph, attributes = _chain_graph()
    ranked = rank_by_centrality(graph, attributes, "betweenness", top_n=10)
    assert all(row["label"] == f"wallet {row['address']}" for row in ranked)
    assert all(row["risk_score"] == 10.0 for row in ranked)


def test_empty_graph_returns_no_results():
    """A chain with no wallets must answer with an empty list, not raise."""
    assert rank_by_centrality(nx.DiGraph(), {}, "pagerank", top_n=10) == []
    assert detect_communities(nx.DiGraph(), {}, min_cluster_size=3) == []


def test_communities_split_two_disconnected_rings():
    """Two groups that never transact with each other are two clusters."""
    graph = nx.DiGraph()
    for ring in (("a", "b", "c"), ("x", "y", "z")):
        for i, node in enumerate(ring):
            graph.add_edge(node, ring[(i + 1) % len(ring)], value_usd=50.0, tx_count=1)
    attributes = {node: {"address": node, "label": None, "risk_score": 40.0} for node in graph}

    clusters = detect_communities(graph, attributes, min_cluster_size=3)

    assert len(clusters) == 2
    memberships = [set(cluster["addresses"]) for cluster in clusters]
    assert {"a", "b", "c"} in memberships
    assert {"x", "y", "z"} in memberships


def test_communities_respect_the_minimum_size():
    graph = nx.DiGraph()
    graph.add_edge("a", "b", value_usd=10.0, tx_count=1)
    attributes = {node: {"address": node, "label": None, "risk_score": 1.0} for node in graph}
    assert detect_communities(graph, attributes, min_cluster_size=3) == []


def test_communities_are_deterministic():
    """Louvain is randomised; a fixed seed is what makes a re-run reproducible."""
    graph = nx.DiGraph()
    for ring in (("a", "b", "c", "d"), ("x", "y", "z", "w")):
        for i, node in enumerate(ring):
            graph.add_edge(node, ring[(i + 1) % len(ring)], value_usd=25.0, tx_count=1)
    attributes = {node: {"address": node, "label": None, "risk_score": 5.0} for node in graph}

    first = detect_communities(graph, attributes, min_cluster_size=2)
    second = detect_communities(graph, attributes, min_cluster_size=2)
    assert first == second


def test_communities_report_average_risk():
    graph = nx.DiGraph()
    for i, node in enumerate(("a", "b", "c")):
        graph.add_edge(node, "abc"[(i + 1) % 3], value_usd=10.0, tx_count=1)
    attributes = {
        "a": {"address": "a", "label": None, "risk_score": 90.0},
        "b": {"address": "b", "label": None, "risk_score": 60.0},
        "c": {"address": "c", "label": None, "risk_score": 30.0},
    }
    clusters = detect_communities(graph, attributes, min_cluster_size=3)
    assert clusters[0]["avg_risk"] == 60.0
