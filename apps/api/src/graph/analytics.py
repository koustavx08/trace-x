"""Graph analytics over the Neo4j wallet graph.

These algorithms used to be called as stored procedures inside Cypher --
`gds.pageRank.stream`, `gds.betweenness.stream` and `algo.louvain.stream`.
None of them ran:

* the Graph Data Science library was never installed (the Neo4j container
  loads only APOC), so every call failed with ProcedureNotFound;
* `algo.*` is the Neo4j 3.x namespace, removed years ago -- that call could
  not have worked even with GDS present;
* the two GDS calls read a named projection, `'wallet-graph'`, that nothing
  in the codebase ever creates.

Rather than take on a ~100MB Java plugin, a projection lifecycle to manage
and a hard version coupling between Neo4j and GDS, the projection is read out
as an ordinary Cypher query and the maths runs in-process. The wallet graph is
small (hundreds of nodes for a case, and each query is scoped to one chain),
so this is comfortably fast, and it keeps the plain `neo4j:5.15-community`
image working everywhere including CI. Community detection and betweenness
come from networkx; PageRank is written out here because networkx routes it
through SciPy (see `_pagerank`).

The graph is projected wallet-to-wallet: TRACE-X stores transactions as nodes
(`Wallet-[:SENT]->Transaction-[:RECEIVED]->Wallet`), and centrality over that
bipartite shape would rank transactions against wallets. Collapsing each
transaction into a direct wallet edge is what makes the score mean "how
central is this wallet in the flow of funds".
"""

from typing import Any

import networkx as nx
import structlog

logger = structlog.get_logger(__name__)

#: Fixed seed so community detection returns the same partition for the same
#: graph. Louvain is randomised, and an investigator re-running a query must
#: not get a different set of clusters each time.
_LOUVAIN_SEED = 20240115

_NODES_QUERY = """
MATCH (w:Wallet {chain: $chain})
RETURN w.address AS address,
       w.label AS label,
       w.risk_score AS risk_score,
       coalesce(w.tx_count, 0) AS tx_count
"""

#: One edge per ordered wallet pair, carrying how many transactions ran between
#: them and how much value did. Self-transfers are dropped: they add nothing to
#: any centrality score and turn into self-loops that Louvain has to special-case.
_EDGES_QUERY = """
MATCH (a:Wallet {chain: $chain})-[:SENT]->(t:Transaction)-[:RECEIVED]->(b:Wallet {chain: $chain})
WHERE a.address <> b.address
RETURN a.address AS source,
       b.address AS target,
       count(*) AS tx_count,
       sum(coalesce(t.value_usd, 0.0)) AS value_usd
"""


async def load_wallet_graph(client: Any, chain: str) -> tuple[nx.DiGraph, dict[str, dict]]:
    """Project the wallet-to-wallet flow graph for one chain.

    Returns the graph and the wallet attributes keyed by address, so callers
    can label their results without a second round trip. Wallets with no
    transfers are kept as isolated nodes -- they legitimately score zero rather
    than being silently missing from the ranking.
    """
    nodes = await client.execute_query(_NODES_QUERY, {"chain": chain})
    edges = await client.execute_query(_EDGES_QUERY, {"chain": chain})

    attributes = {record["address"]: dict(record) for record in nodes}

    graph = nx.DiGraph()
    graph.add_nodes_from(attributes)
    for record in edges:
        graph.add_edge(
            record["source"],
            record["target"],
            tx_count=record["tx_count"],
            value_usd=float(record["value_usd"] or 0.0),
        )

    logger.debug(
        "wallet_graph_projected",
        chain=chain,
        nodes=graph.number_of_nodes(),
        edges=graph.number_of_edges(),
    )
    return graph, attributes


def rank_by_centrality(
    graph: nx.DiGraph,
    attributes: dict[str, dict],
    algorithm: str,
    top_n: int,
) -> list[dict[str, Any]]:
    """Score every wallet and return the `top_n` most central.

    `pagerank` keeps the damping factor and iteration cap the GDS call used, so
    scores stay comparable with anything recorded before this change.
    """
    if graph.number_of_nodes() == 0:
        return []

    if algorithm == "pagerank":
        # value_usd weights the flow: a wallet that received a large share of
        # the traced funds is more central than one that saw many dust hops.
        scores = _pagerank(graph, damping=0.85, iterations=20)
    elif algorithm == "betweenness":
        # Unweighted: here an edge weight would be read as *distance*, so
        # weighting by value would make the largest transfers the longest path.
        scores = nx.betweenness_centrality(graph)
    else:
        scores = {node: float(graph.degree(node)) for node in graph}

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_n]
    return [
        {
            "address": address,
            "label": attributes.get(address, {}).get("label"),
            "risk_score": attributes.get(address, {}).get("risk_score"),
            "score": float(score),
        }
        for address, score in ranked
    ]


def _pagerank(
    graph: nx.DiGraph,
    damping: float = 0.85,
    iterations: int = 20,
) -> dict[str, float]:
    """PageRank by power iteration, weighted by USD value moved.

    Written out rather than calling `nx.pagerank`, which dispatches to a
    SciPy sparse implementation and raises ModuleNotFoundError without numpy
    and scipy installed. Those are a heavy pair of dependencies to add for one
    algorithm on a graph of a few hundred nodes, and `betweenness_centrality`
    and `louvain_communities` are pure Python already.

    Iterating a fixed number of times also matches what the GDS call this
    replaced did with `maxIterations: 20` -- networkx treats that argument as a
    convergence budget instead, and raises PowerIterationFailedConvergence if
    the graph has not settled within it.
    """
    nodes = list(graph)
    count = len(nodes)
    if count == 0:
        return {}

    # Out-weights per node, falling back to edge counts where a wallet's
    # transfers carry no USD valuation at all -- otherwise those wallets look
    # like dangling nodes and leak their rank to the whole graph.
    out_weight: dict[str, float] = {}
    for node in nodes:
        total = sum(
            float(data.get("value_usd") or 0.0) for _, _, data in graph.out_edges(node, data=True)
        )
        if total <= 0.0:
            total = float(graph.out_degree(node))
        out_weight[node] = total

    scores = dict.fromkeys(nodes, 1.0 / count)
    teleport = (1.0 - damping) / count

    for _ in range(iterations):
        updated = dict.fromkeys(nodes, teleport)

        # A wallet with no outgoing transfers is a sink; spreading its rank
        # evenly is what keeps the scores summing to one.
        dangling = sum(scores[node] for node in nodes if out_weight[node] <= 0.0)
        if dangling:
            share = damping * dangling / count
            for node in nodes:
                updated[node] += share

        for source, target, data in graph.edges(data=True):
            total = out_weight[source]
            if total <= 0.0:
                continue
            weight = float(data.get("value_usd") or 0.0)
            if weight <= 0.0:
                weight = 1.0
            updated[target] += damping * scores[source] * weight / total

        scores = updated

    return scores


def detect_communities(
    graph: nx.DiGraph,
    attributes: dict[str, dict],
    min_cluster_size: int,
) -> list[dict[str, Any]]:
    """Group wallets into communities, largest average risk first.

    Louvain needs an undirected graph: direction of funds does not change who
    belongs to a cluster, and the directed form would split a sender from the
    address it swept into.
    """
    if graph.number_of_nodes() == 0:
        return []

    undirected = graph.to_undirected()
    communities = nx.community.louvain_communities(
        undirected, weight="value_usd", seed=_LOUVAIN_SEED
    )

    clusters = []
    for index, members in enumerate(sorted(communities, key=len, reverse=True)):
        if len(members) < min_cluster_size:
            continue
        addresses = sorted(members)
        risks = [
            float(attributes[address]["risk_score"])
            for address in addresses
            if attributes.get(address, {}).get("risk_score") is not None
        ]
        clusters.append(
            {
                "community": index,
                "size": len(addresses),
                "addresses": addresses,
                "avg_risk": round(sum(risks) / len(risks), 2) if risks else None,
                "sample_addresses": addresses[:5],
            }
        )

    clusters.sort(key=lambda c: (c["avg_risk"] is None, -(c["avg_risk"] or 0.0)))
    return clusters
