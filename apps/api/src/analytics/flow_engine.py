"""Flow-weighted shortest path and max-flow / min-cut over a set of transfers.

Implements spec §2.2. The graph layer's Dijkstra runs with a uniform edge
weight of 1.0, so it optimises for the fewest wallet hops -- which is exactly
the wrong answer in a laundering case: a one-hop $10 decoy transfer outranks
the two-hop $1,000,000 pipeline the money actually took. Weighting each edge by
the inverse log of the USD moved makes a high-value hop *cheap* to traverse, so
the shortest path becomes the main money corridor rather than the shortest
wire.

Max-flow answers the second question an investigator asks: not "which route did
it take" but "how much could possibly have reached this exchange deposit, and
which handful of edges, if frozen, would stop all of it". The min-cut is that
freeze list -- the saturated edges whose combined capacity equals the whole
throughput of the network between the suspect and the sink.

The module is deliberately pure: it takes `Transfer` records and returns value
objects, with no Neo4j, Postgres or provider calls, so it is testable without
any infrastructure and can be fed from either store.
"""

from __future__ import annotations

import heapq
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

import networkx as nx
import structlog

from src.analytics.types import Transfer, normalize_address

logger = structlog.get_logger(__name__)

#: Weight handed to an edge that moved (effectively) nothing. W(e) diverges as
#: the value approaches zero, and an infinite weight would make Dijkstra's
#: arithmetic undefined, so the curve is capped: a valueless hop stays the most
#: expensive edge in the graph without ever becoming untraversable. It is not
#: dropped, because a zero-value hop can still be the only link in a chain.
_MAX_WEIGHT = 1e6

#: The denominator at which the cap above takes over, kept in sync with it so
#: the function stays continuous instead of stepping at an arbitrary value.
_MIN_DENOMINATOR = 1.0 / _MAX_WEIGHT

#: Flows below a ten-billionth of a dollar are floating-point residue from the
#: max-flow solver, not money. Treating them as real would make the path
#: decomposition loop on edges carrying nothing.
_FLOW_EPSILON = 1e-9

#: How many routes the flow decomposition reports. An investigator needs the
#: principal corridors for a warrant, not an exhaustive enumeration of every
#: capillary carrying a dollar of the total.
_MAX_FLOW_PATHS = 5


def value_weight(value_usd: float) -> float:
    """W(e) = 1 / log10(value + 1) -- the inverse-log edge weight from §2.2.

    Returns a *distance*: high value means low cost, so Dijkstra follows the
    corridor that moved the money. The log keeps the scale sane -- a $1M hop is
    roughly four times cheaper than a $10 one, not a hundred thousand times,
    which stops a single whale transfer from making every other route
    unreachable.

    Always finite and strictly positive, including for 0, negative and
    non-finite inputs: provider data is not trusted to be clean, and an
    unpriced or corrupt transfer must not poison the whole search with NaN.
    """
    if not math.isfinite(value_usd) or value_usd <= 0.0:
        return _MAX_WEIGHT

    denominator = math.log10(value_usd + 1.0)
    if denominator <= _MIN_DENOMINATOR:
        return _MAX_WEIGHT
    return 1.0 / denominator


def build_flow_graph(transfers: Sequence[Transfer]) -> nx.DiGraph:
    """Collapse transfers into a wallet-to-wallet flow network.

    Parallel transfers between the same pair aggregate into one edge. Keeping
    them separate would understate the corridor: a smurfing run of 200 x $5,000
    hops between the same two wallets is one $1,000,000 pipeline, and both the
    edge weight and the flow capacity have to see it that way. The individual
    hashes are kept on the edge so the aggregate stays auditable back to
    on-chain evidence.

    Self-transfers and zero-value transfers are dropped: neither moves money
    between wallets, and a self-loop only confuses the flow solver.
    """
    grouped: dict[tuple[str, str], list[Transfer]] = defaultdict(list)
    for transfer in transfers:
        if transfer.from_address == transfer.to_address:
            continue
        if not math.isfinite(transfer.value_usd) or transfer.value_usd <= 0.0:
            continue
        grouped[(transfer.from_address, transfer.to_address)].append(transfer)

    # Subscripted for networkx's stubs, which make DiGraph generic. Safe
    # unquoted: annotations on local variables are never evaluated (PEP 526).
    graph: nx.DiGraph[str] = nx.DiGraph()

    # Insertion is sorted so that node and edge iteration order -- and with it
    # every tie-break in the searches below -- depends only on the addresses
    # involved, never on the order the caller happened to read rows in.
    for pair in sorted(grouped):
        legs = sorted(grouped[pair], key=lambda leg: (leg.timestamp, leg.tx_hash))
        total = float(sum(leg.value_usd for leg in legs))
        graph.add_edge(
            pair[0],
            pair[1],
            # Same number under two names: `capacity_usd` is what the flow
            # solver is pointed at, `value_usd` is the forensic reading of it.
            capacity_usd=total,
            value_usd=total,
            weight=value_weight(total),
            tx_count=len(legs),
            tx_hashes=tuple(leg.tx_hash for leg in legs),
            first_seen=legs[0].timestamp,
            last_seen=legs[-1].timestamp,
        )

    logger.debug(
        "flow_graph_built",
        transfers=len(transfers),
        nodes=graph.number_of_nodes(),
        edges=graph.number_of_edges(),
    )
    return graph


@dataclass(frozen=True, slots=True)
class PathResult:
    """One route through the flow network, ready to serialise into a report."""

    nodes: tuple[str, ...]
    edges: tuple[dict[str, Any], ...]
    #: The USD this route accounts for: the summed value of its aggregated
    #: edges for a discovered path, or the flow assigned to the route when it
    #: came out of a max-flow decomposition -- there the same dollar crossing
    #: three hops must be counted once, not three times.
    total_value_usd: float
    hops: int
    #: Total inverse-log distance, i.e. what Dijkstra minimised. Lower means a
    #: higher-value corridor, not a shorter one.
    weight: float


@dataclass(frozen=True, slots=True)
class FlowResult:
    """Throughput between two wallets, plus the edges that would stop it."""

    source: str
    target: str
    max_flow_usd: float
    #: Saturated edges crossing the minimum cut -- the freeze list.
    min_cut_edges: tuple[tuple[str, str], ...]
    #: Capacity of the narrowest edge in that cut: the single choke point.
    bottleneck_usd: float
    flow_paths: tuple[PathResult, ...]


def flow_weighted_path(
    transfers: Sequence[Transfer],
    source: str,
    target: str,
    *,
    max_hops: int = 8,
) -> PathResult | None:
    """Cheapest route from `source` to `target` under the inverse-log weight.

    Returns None rather than raising when either wallet is absent from the
    transfer set, when nothing connects them, or when the only connection is
    longer than `max_hops`. All three are ordinary answers in an investigation
    ("these two wallets are not linked in the data we hold"), not faults, and
    the API layer renders them the same way.

    The hop cap is applied after the search, not during it: a cheaper route
    that happens to be long is still the route the money took, and truncating
    the search would silently return a worse one instead of saying "no path
    within the horizon you asked for".
    """
    start = normalize_address(source)
    end = normalize_address(target)
    graph = build_flow_graph(transfers)

    # A wallet is its own trivial path; reporting that as a laundering corridor
    # would be noise, so it is treated as "no route" like any other non-answer.
    if start == end or start not in graph or end not in graph:
        return None

    try:
        found = nx.single_source_dijkstra(graph, start, end, weight="weight")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

    # Called with an explicit target, networkx returns one (distance, path)
    # pair; the stubs widen the return to the all-targets dict form it takes
    # when `target` is omitted, which is not the shape reachable from here.
    weight, nodes = cast(tuple[float, list[str]], found)

    hops = len(nodes) - 1
    if hops > max_hops:
        logger.debug("flow_path_exceeds_hop_limit", hops=hops, max_hops=max_hops)
        return None

    edges = tuple(
        _edge_descriptor(nodes[index], nodes[index + 1], graph[nodes[index]][nodes[index + 1]])
        for index in range(hops)
    )
    return PathResult(
        nodes=tuple(nodes),
        edges=edges,
        total_value_usd=float(sum(edge["value_usd"] for edge in edges)),
        hops=hops,
        weight=float(weight),
    )


def max_flow_min_cut(transfers: Sequence[Transfer], source: str, target: str) -> FlowResult:
    """Maximum USD throughput from `source` to `target`, and the cut that ends it.

    The answer is an upper bound on what *could* have reached the sink given
    the observed transfers, which is the number that justifies a freeze
    requisition: the min-cut edges are exactly the set whose seizure drops that
    bound to zero, so they are the addresses to name in the notice.

    Never raises. A wallet that is not in the data, or is not connected to the
    other, yields a zeroed result -- the honest reading of "no traceable
    capacity between these two", which callers render without special-casing.
    """
    start = normalize_address(source)
    end = normalize_address(target)
    empty = FlowResult(
        source=start,
        target=end,
        max_flow_usd=0.0,
        min_cut_edges=(),
        bottleneck_usd=0.0,
        flow_paths=(),
    )

    graph = build_flow_graph(transfers)
    if start == end or start not in graph or end not in graph:
        return empty

    try:
        flow_value, flow_dict = nx.maximum_flow(graph, start, end, capacity="capacity_usd")
        _, (reachable, _unreachable) = nx.minimum_cut(graph, start, end, capacity="capacity_usd")
    except (nx.NetworkXError, nx.NetworkXUnbounded):
        # Disconnected endpoints and degenerate networks are answers, not bugs.
        return empty

    if flow_value <= _FLOW_EPSILON:
        return empty

    # The cut is the frontier of the source-side partition: every edge leaving
    # it is saturated, and together they carry the entire max flow.
    cut_edges = tuple(
        sorted(
            (tail, head)
            for tail in reachable
            for head in graph.successors(tail)
            if head not in reachable
        )
    )
    bottleneck = (
        min(graph[tail][head]["capacity_usd"] for tail, head in cut_edges) if cut_edges else 0.0
    )

    result = FlowResult(
        source=start,
        target=end,
        max_flow_usd=float(flow_value),
        min_cut_edges=cut_edges,
        bottleneck_usd=float(bottleneck),
        flow_paths=_decompose_flow(graph, flow_dict, start, end),
    )
    logger.debug(
        "max_flow_computed",
        source=start,
        target=end,
        max_flow_usd=result.max_flow_usd,
        cut_edges=len(cut_edges),
        flow_paths=len(result.flow_paths),
    )
    return result


def _edge_descriptor(
    tail: str,
    head: str,
    data: dict[str, Any],
    flow_usd: float | None = None,
) -> dict[str, Any]:
    """JSON-ready view of one aggregated edge.

    Timestamps go out as ISO-8601 strings and hashes as a list because these
    descriptors are embedded verbatim in API responses and in the evidence
    export, which cannot carry datetimes or tuples.
    """
    descriptor: dict[str, Any] = {
        "from_address": tail,
        "to_address": head,
        "value_usd": float(data["value_usd"]),
        "capacity_usd": float(data["capacity_usd"]),
        "weight": float(data["weight"]),
        "tx_count": int(data["tx_count"]),
        "tx_hashes": list(data["tx_hashes"]),
        "first_seen": _isoformat(data["first_seen"]),
        "last_seen": _isoformat(data["last_seen"]),
    }
    if flow_usd is not None:
        # How much of the max flow this edge carries on this particular route,
        # which is what the report shows next to the observed total.
        descriptor["flow_usd"] = float(flow_usd)
    return descriptor


def _isoformat(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment is not None else None


def _decompose_flow(
    graph: nx.DiGraph,
    flow_dict: dict[str, dict[str, float]],
    source: str,
    target: str,
) -> tuple[PathResult, ...]:
    """Split the max-flow solution into the routes that carry it, widest first.

    A flow value alone is not evidence; an investigator has to be able to point
    at the wallets it travelled through. Peeling off the widest route each time
    surfaces the principal laundering corridors first and leaves the dust for
    last, which is the order a report wants them in.
    """
    residual: dict[str, dict[str, float]] = defaultdict(dict)
    for tail, heads in flow_dict.items():
        for head, amount in heads.items():
            if not graph.has_edge(tail, head):
                continue
            # Net off any flow the solver routed back the other way: a pair of
            # antiparallel edges both "carrying" money is bookkeeping, not a
            # real round trip, and would show up as a phantom corridor.
            net = float(amount) - float(flow_dict.get(head, {}).get(tail, 0.0))
            if net > _FLOW_EPSILON:
                residual[tail][head] = net

    paths: list[PathResult] = []
    for _ in range(_MAX_FLOW_PATHS):
        nodes = _widest_path(residual, source, target)
        if nodes is None:
            break

        carried = min(residual[nodes[index]][nodes[index + 1]] for index in range(len(nodes) - 1))
        if carried <= _FLOW_EPSILON:
            break

        edges: list[dict[str, Any]] = []
        for index in range(len(nodes) - 1):
            tail, head = nodes[index], nodes[index + 1]
            residual[tail][head] -= carried
            if residual[tail][head] <= _FLOW_EPSILON:
                del residual[tail][head]
            edges.append(_edge_descriptor(tail, head, graph[tail][head], flow_usd=carried))

        paths.append(
            PathResult(
                nodes=tuple(nodes),
                edges=tuple(edges),
                total_value_usd=float(carried),
                hops=len(nodes) - 1,
                weight=float(sum(edge["weight"] for edge in edges)),
            )
        )

    return tuple(paths)


def _widest_path(
    residual: dict[str, dict[str, float]],
    source: str,
    target: str,
) -> list[str] | None:
    """Maximum-bottleneck path through the remaining flow, or None if drained.

    Dijkstra with `min` in place of `+` and a max-heap: the "distance" to a
    node is the largest amount that can still reach it. Neighbours are visited
    in address order and a node is only relaxed on a strictly wider candidate,
    so equal-capacity routes always resolve the same way -- the same case file
    must not produce a different corridor on a re-run.
    """
    best: dict[str, float] = {source: math.inf}
    previous: dict[str, str] = {}
    visited: set[str] = set()
    heap: list[tuple[float, str]] = [(-math.inf, source)]

    while heap:
        negative_width, node = heapq.heappop(heap)
        if node in visited:
            continue
        visited.add(node)
        if node == target:
            break

        width = -negative_width
        for neighbour, amount in sorted(residual.get(node, {}).items()):
            if neighbour in visited or amount <= _FLOW_EPSILON:
                continue
            candidate = min(width, amount)
            if candidate > best.get(neighbour, 0.0):
                best[neighbour] = candidate
                previous[neighbour] = node
                heapq.heappush(heap, (-candidate, neighbour))

    if target not in visited:
        return None

    nodes = [target]
    while nodes[-1] != source:
        nodes.append(previous[nodes[-1]])
    nodes.reverse()
    return nodes


__all__ = [
    "FlowResult",
    "PathResult",
    "build_flow_graph",
    "flow_weighted_path",
    "max_flow_min_cut",
    "value_weight",
]
