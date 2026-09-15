"""Temporal subgraph / laundering-motif mining (spec 2.4).

Launderers do not hide in the *values* they move -- those are trivially
randomised -- they hide in plain sight in the *shape* and *timing* of the
movement. Three shapes account for most of what an investigator actually
chases in a task-scam or investment-fraud case:

* **fan-out / fan-in (smurfing)** -- one source splits a seized amount across
  N mule wallets which each forward their slice into a single exchange
  deposit, so no individual hop trips a reporting threshold;
* **peel chain** -- value walks down a corridor of hops, each hop shaving a
  small slice off to a VASP (cash-out) while forwarding the bulk onward;
* **cycle / U-turn** -- funds return to an address they already visited,
  which is wash trading or an attempt to fabricate trading history.

The spec mandates **VF2 subgraph isomorphism** for the structural half of the
work, with a temporal constraint layered on top:

    Delta t = t(tx_{i+1}) - t(tx_i) <= T_max

Structure alone is not evidence: a "source -> 4 mules -> exchange" shape that
plays out over eight months is an ordinary payroll fan-out. It is the shape
*plus* the clock that makes it a laundering motif, so every detector here
enforces both and reports the observed span it matched on.

This module is pure: it takes `Transfer` records and returns `MotifMatch`
records. No Neo4j, no Postgres, no network -- the caller normalises whatever
store it reads from into `Transfer` first (see `src.analytics.types`).
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from itertools import islice
from typing import Any

import networkx as nx
import structlog
from networkx.algorithms import isomorphism as iso

from src.analytics.types import Transfer

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Work caps.
#
# Every one of these bounds an otherwise exponential search so that a graph of
# a few thousand transfers still answers in a couple of seconds. They are
# deliberately generous relative to real case data (a traced case is hundreds
# of wallets, not millions) and every truncation is applied to a
# deterministically sorted list, so capping never makes the output flaky --
# only, in a pathological graph, incomplete. Truncation is logged.
# ---------------------------------------------------------------------------

#: Source/sink pairs carried into the VF2 stage, strongest (most shared mules)
#: first. Pair enumeration itself is cheap; VF2 is not.
_MAX_CANDIDATE_PAIRS = 500

#: Widest fan template we build. VF2's cost grows with template size, and a
#: 9-mule smurf is already proven at 8 -- past `min_mules` extra mules change
#: the confidence, not the verdict.
_MAX_TEMPLATE_MULES = 8

#: Per (source, mule, sink) leg, how many parallel transfers we pair up when
#: looking for a temporally coherent in/out hop. Repeat hops between the same
#: two wallets are common; combinatorially pairing all of them is not useful.
_MAX_TX_PER_EDGE = 8

#: How far a peel chain may be walked before we call it a corridor and stop.
_MAX_CHAIN_DEPTH = 64

#: Cycles pulled from `nx.simple_cycles`. A dense graph contains astronomically
#: many bounded cycles; the enumeration is lazy, so we stop drawing from it.
_MAX_CYCLES = 500

#: Alternative starting transfers tried when timing a cycle's hops.
_MAX_CYCLE_STARTS = 8

#: Confidence ceiling. A motif match is corroborating evidence, never proof --
#: legitimate business produces every one of these shapes occasionally -- so no
#: detector is allowed to report certainty.
_CONFIDENCE_CEILING = 0.95


@dataclass(frozen=True)
class MotifMatch:
    """One laundering motif found in the transfer graph.

    `window_seconds` is the *observed* span of the match (last timestamp minus
    first), not the window it was searched with: an investigator writing this
    into a report needs to say how tight the timing actually was.
    """

    motif: str
    addresses: tuple[str, ...]
    tx_hashes: tuple[str, ...]
    value_usd: float
    confidence: float
    window_seconds: float
    detail: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shared graph preparation
# ---------------------------------------------------------------------------


def _clean(transfers: Sequence[Transfer]) -> list[Transfer]:
    """Drop what cannot carry a laundering signal and impose a stable order.

    Zero/negative-value transfers are approval calls, failed sends and dust
    sprays -- they create edges that no money crossed, which is exactly how a
    motif detector hallucinates a mule network. Self-loops are internal
    accounting (a contract moving its own balance) and would make every
    address a one-node cycle.
    """
    return sorted(
        (t for t in transfers if t.value_usd > 0 and t.from_address != t.to_address),
        key=lambda t: (t.timestamp, t.tx_hash, t.from_address, t.to_address),
    )


def _build_graph(cleaned: Sequence[Transfer]) -> nx.DiGraph:
    """Collapse transfers onto a wallet-to-wallet DiGraph.

    VF2 needs a simple digraph, so parallel transfers between the same pair
    live on one edge under `transfers` (kept in the timestamp order `_clean`
    established). Insertion order follows that same sorted order, which is
    what makes `nx.simple_cycles` enumerate deterministically below.
    """
    graph: nx.DiGraph[str] = nx.DiGraph()
    for transfer in cleaned:
        edge = graph.get_edge_data(transfer.from_address, transfer.to_address)
        if edge is None:
            graph.add_edge(transfer.from_address, transfer.to_address, transfers=[transfer])
        else:
            edge["transfers"].append(transfer)
    return graph


def _span_seconds(moments: Sequence[datetime]) -> float:
    return (max(moments) - min(moments)).total_seconds() if moments else 0.0


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _tx_hashes(transfers: Sequence[Transfer]) -> tuple[str, ...]:
    ordered = sorted(transfers, key=lambda t: (t.timestamp, t.tx_hash))
    return tuple(t.tx_hash for t in ordered)


# ---------------------------------------------------------------------------
# 1. Fan-out / fan-in (smurfing) -- VF2
# ---------------------------------------------------------------------------


def _fan_template(mule_count: int) -> nx.DiGraph:
    """The smurfing template: one source -> N mules -> one sink."""
    template: nx.DiGraph[str] = nx.DiGraph()
    for index in range(mule_count):
        mule = f"m{index}"
        template.add_edge("source", mule)
        template.add_edge(mule, "sink")
    return template


def _fan_candidates(graph: nx.DiGraph, min_mules: int) -> list[tuple[tuple[str, str], set[str]]]:
    """Shortlist (source, sink) pairs that could possibly host a fan template.

    VF2 is exponential in the general case, so it must never see the whole
    case graph: on a few thousand wallets the matcher would still be
    backtracking when the investigation is over. Degree is a cheap necessary
    condition -- a source needs `min_mules` out-edges and a sink needs
    `min_mules` in-edges -- and walking source -> mule -> sink directly yields
    the shared-mule set for each pair in roughly O(E * avg out-degree). VF2
    then runs only on the handful of nodes induced by a surviving pair, where
    it is cheap and where its answer is the one we actually want.
    """
    shared: dict[tuple[str, str], set[str]] = {}
    for source in graph:
        if graph.out_degree(source) < min_mules:
            continue
        for mule in graph.successors(source):
            for sink in graph.successors(mule):
                if sink == source:
                    continue
                if graph.in_degree(sink) < min_mules:
                    continue
                shared.setdefault((source, sink), set()).add(mule)

    candidates = [(pair, mules) for pair, mules in shared.items() if len(mules) >= min_mules]
    # Strongest fans first, address-ordered for ties, so the cap below is
    # deterministic and keeps the most incriminating pairs.
    candidates.sort(key=lambda item: (-len(item[1]), item[0]))
    if len(candidates) > _MAX_CANDIDATE_PAIRS:
        logger.info(
            "motif_fan_candidates_truncated",
            found=len(candidates),
            kept=_MAX_CANDIDATE_PAIRS,
        )
        candidates = candidates[:_MAX_CANDIDATE_PAIRS]
    return candidates


def _confirm_fan_template(
    graph: nx.DiGraph,
    source: str,
    sink: str,
    mules: set[str],
    min_mules: int,
) -> int:
    """Widest fan template VF2 can embed in this pair's induced subgraph.

    Templates are built from `min_mules` upward and the search stops at the
    first width that fails: a source cannot feed k+1 mules into a sink if it
    cannot feed k, so anything wider is unreachable. Monomorphism rather than
    induced isomorphism is the right relation here -- mules that also pay each
    other are still mules, and an induced match would reject the whole fan
    because of one such extra edge.
    """
    ordered = sorted(mules)[:_MAX_TEMPLATE_MULES]
    induced = graph.subgraph([source, sink, *ordered])
    confirmed = 0
    for width in range(min_mules, len(ordered) + 1):
        matcher = iso.DiGraphMatcher(induced, _fan_template(width))
        if not matcher.subgraph_is_monomorphic():
            break
        confirmed = width
    return confirmed


def _pair_hops(
    graph: nx.DiGraph,
    source: str,
    mule: str,
    sink: str,
    *,
    window_seconds: int,
    value_tolerance: float,
) -> tuple[Transfer, Transfer, float] | None:
    """Best in/out hop pair for one mule, or None if it never behaved like one.

    A mule holds funds briefly and forwards substantially what it received;
    an address that received 10 USD from the source and sent 40 000 USD to the
    exchange a month later is a coincidence of topology, not a leg of the fan.
    """
    inbound = graph[source][mule]["transfers"][:_MAX_TX_PER_EDGE]
    outbound = graph[mule][sink]["transfers"][:_MAX_TX_PER_EDGE]

    best: tuple[tuple[float, float, str], Transfer, Transfer, float] | None = None
    for received in inbound:
        for forwarded in outbound:
            gap = (forwarded.timestamp - received.timestamp).total_seconds()
            # Funds cannot be forwarded before they arrive.
            if gap < 0 or gap > window_seconds:
                continue
            deviation = abs(forwarded.value_usd - received.value_usd) / received.value_usd
            if deviation > value_tolerance:
                continue
            key = (gap, deviation, forwarded.tx_hash)
            if best is None or key < best[0]:
                best = (key, received, forwarded, deviation)
    if best is None:
        return None
    return best[1], best[2], best[3]


def _temporal_runs(
    legs: dict[str, tuple[Transfer, Transfer, float]],
    window_seconds: int,
) -> list[list[str]]:
    """Split a fan's legs into bursts separated by more than the window.

    This is where `Delta t <= T_max` bites. All the transfers of all the legs
    are laid on one timeline and cut wherever consecutive events are further
    apart than the window; a mule counts towards a burst only if *both* of its
    hops fall inside it. The classic failure this catches: the fan-out happens
    in one minute and the fan-in a week later, which is two bursts holding one
    orphaned hop each and therefore no complete mule in either.
    """
    events: list[tuple[datetime, str, str]] = []
    for mule, (received, forwarded, _) in legs.items():
        events.append((received.timestamp, received.tx_hash, mule))
        events.append((forwarded.timestamp, forwarded.tx_hash, mule))
    events.sort()

    runs: list[list[tuple[datetime, str, str]]] = []
    current: list[tuple[datetime, str, str]] = []
    for event in events:
        if current and (event[0] - current[-1][0]).total_seconds() > window_seconds:
            runs.append(current)
            current = []
        current.append(event)
    if current:
        runs.append(current)

    complete: list[list[str]] = []
    for run in runs:
        counts: dict[str, int] = {}
        for _, _, mule in run:
            counts[mule] = counts.get(mule, 0) + 1
        complete.append(sorted(mule for mule, count in counts.items() if count == 2))
    return complete


def detect_fan_out_fan_in(
    transfers: Sequence[Transfer],
    *,
    window_seconds: int = 1800,
    min_mules: int = 3,
    value_tolerance: float = 0.25,
) -> list[MotifMatch]:
    """Find smurfing fans: source -> N mules -> one collection point.

    Structural matching is VF2 (`DiGraphMatcher`) against a generated
    source -> N mules -> sink template; the temporal and value constraints are
    then applied to the matched pair to decide which mules genuinely
    participated in one burst.
    """
    cleaned = _clean(transfers)
    if not cleaned:
        return []

    graph = _build_graph(cleaned)
    matches: list[MotifMatch] = []

    for (source, sink), mules in _fan_candidates(graph, min_mules):
        if _confirm_fan_template(graph, source, sink, mules, min_mules) < min_mules:
            continue

        legs: dict[str, tuple[Transfer, Transfer, float]] = {}
        for mule in sorted(mules):
            hops = _pair_hops(
                graph,
                source,
                mule,
                sink,
                window_seconds=window_seconds,
                value_tolerance=value_tolerance,
            )
            if hops is not None:
                legs[mule] = hops
        if len(legs) < min_mules:
            continue

        for participants in _temporal_runs(legs, window_seconds):
            if len(participants) < min_mules:
                continue

            burst = {mule: legs[mule] for mule in participants}
            matched = [t for leg in burst.values() for t in leg[:2]]
            fan_out = sum(leg[0].value_usd for leg in burst.values())
            fan_in = sum(leg[1].value_usd for leg in burst.values())
            deviations = [leg[2] for leg in burst.values()]
            gaps = [(leg[1].timestamp - leg[0].timestamp).total_seconds() for leg in burst.values()]
            span = _span_seconds([t.timestamp for t in matched])

            # More mules is a stronger smurf; tighter value pass-through and a
            # tighter burst both push towards deliberate layering rather than
            # an ordinary payout that happens to converge.
            breadth = _clamp(len(participants) / (min_mules * 2))
            fidelity = _clamp(
                1.0 - (sum(deviations) / len(deviations)) / value_tolerance
                if value_tolerance > 0
                else 1.0
            )
            tightness = _clamp(1.0 - span / window_seconds) if window_seconds > 0 else 0.0

            matches.append(
                MotifMatch(
                    motif="fan_out_fan_in",
                    addresses=(source, *participants, sink),
                    tx_hashes=_tx_hashes(matched),
                    value_usd=round(fan_out, 2),
                    confidence=round(
                        _CONFIDENCE_CEILING * (0.45 * breadth + 0.35 * fidelity + 0.20 * tightness),
                        3,
                    ),
                    window_seconds=span,
                    detail={
                        "source": source,
                        "sink": sink,
                        "mule_count": len(participants),
                        "mules": participants,
                        "fan_out_usd": round(fan_out, 2),
                        "fan_in_usd": round(fan_in, 2),
                        "max_hop_seconds": max(gaps),
                        "mean_value_deviation": round(sum(deviations) / len(deviations), 4),
                    },
                )
            )

    return matches


# ---------------------------------------------------------------------------
# 2. Peel chain
# ---------------------------------------------------------------------------


def _walk_peel_chain(
    outgoing: dict[str, list[Transfer]],
    entry: Transfer,
    *,
    min_length: int,
    peel_ratio_max: float,
    window_seconds: int,
) -> tuple[list[Transfer], list[Transfer], list[str], list[float]] | None:
    """Walk one corridor forward from `entry`, peeling as we go.

    At each hop the wallet must do two things at once: forward the bulk of
    what it just received (>= 1 - peel_ratio_max of it) and shave a small
    slice (<= peel_ratio_max) off to a side address, typically a VASP deposit
    where it gets cashed out. A hop that splits value evenly is a fan-out, not
    a peel, and a hop that sends everything onward is just a relay -- neither
    extends the chain.
    """
    path = [entry.from_address, entry.to_address]
    visited = set(path)
    forwards = [entry]
    peels: list[Transfer] = []
    ratios: list[float] = []

    node = entry.to_address
    held = entry.value_usd
    clock = entry.timestamp

    for _ in range(_MAX_CHAIN_DEPTH):
        options = [
            candidate
            for candidate in outgoing.get(node, ())
            if candidate.timestamp >= clock
            and (candidate.timestamp - entry.timestamp).total_seconds() <= window_seconds
            and candidate.to_address not in visited
        ]
        if len(options) < 2:
            break

        forward = max(options, key=lambda t: (t.value_usd, t.tx_hash))
        forward_ratio = forward.value_usd / held
        if forward_ratio < 1.0 - peel_ratio_max:
            break

        peel = max(
            (
                candidate
                for candidate in options
                if candidate.tx_hash != forward.tx_hash
                and 0 < candidate.value_usd / held <= peel_ratio_max
            ),
            key=lambda t: (t.value_usd, t.tx_hash),
            default=None,
        )
        if peel is None:
            break

        forwards.append(forward)
        peels.append(peel)
        ratios.append(peel.value_usd / held)
        path.append(forward.to_address)
        visited.add(forward.to_address)
        visited.add(peel.to_address)
        node = forward.to_address
        held = forward.value_usd
        clock = forward.timestamp

    if len(peels) < min_length:
        return None
    return forwards, peels, path, ratios


def detect_peel_chain(
    transfers: Sequence[Transfer],
    *,
    min_length: int = 3,
    peel_ratio_max: float = 0.4,
    window_seconds: int = 86400,
) -> list[MotifMatch]:
    """Find peel chains: a corridor of hops each shaving a slice to a VASP.

    The walk is greedy (largest onward transfer is the forward, largest
    qualifying slice is the peel) rather than exhaustive: a peel chain is by
    construction a single dominant path, and enumerating every branch of a
    hub-heavy graph is what makes this kind of search blow up.
    """
    cleaned = _clean(transfers)
    if not cleaned:
        return []

    outgoing: dict[str, list[Transfer]] = {}
    for transfer in cleaned:
        outgoing.setdefault(transfer.from_address, []).append(transfer)

    chains: list[tuple[list[Transfer], list[Transfer], list[str], list[float]]] = []
    for entry in cleaned:
        # Only a wallet that both forwards and peels can continue a chain, so
        # skip seeds whose recipient has fewer than two outgoing transfers.
        if len(outgoing.get(entry.to_address, ())) < 2:
            continue
        walked = _walk_peel_chain(
            outgoing,
            entry,
            min_length=min_length,
            peel_ratio_max=peel_ratio_max,
            window_seconds=window_seconds,
        )
        if walked is not None:
            chains.append(walked)

    # Every hop of a chain is itself a valid entry, so the same corridor is
    # walked once per hop, each walk a suffix of the last. Keep only maximal
    # corridors: longest first, dropping any whose hops are already covered.
    chains.sort(key=lambda c: (-len(c[1]), -sum(t.value_usd for t in c[0]), c[2]))
    kept: list[tuple[list[Transfer], list[Transfer], list[str], list[float]]] = []
    covered: list[set[str]] = []
    for chain in chains:
        hashes = {t.tx_hash for t in chain[0]}
        if any(hashes <= seen for seen in covered):
            continue
        kept.append(chain)
        covered.append(hashes)

    matches: list[MotifMatch] = []
    for forwards, peels, path, ratios in kept:
        matched = [*forwards, *peels]
        span = _span_seconds([t.timestamp for t in matched])
        peel_addresses = sorted({t.to_address for t in peels})

        # A longer corridor with consistently thin peels is the signature; a
        # chain that only just clears the ratio ceiling is closer to an
        # ordinary split payment.
        length_score = _clamp(len(peels) / (min_length * 2))
        thinness = _clamp(
            1.0 - (sum(ratios) / len(ratios)) / peel_ratio_max if peel_ratio_max > 0 else 1.0
        )
        tightness = _clamp(1.0 - span / window_seconds) if window_seconds > 0 else 0.0

        matches.append(
            MotifMatch(
                motif="peel_chain",
                # Corridor in flow order first, then the side addresses that
                # took the peels -- the chain is the story, the VASPs are the
                # exits an investigator has to subpoena.
                addresses=(*path, *peel_addresses),
                tx_hashes=_tx_hashes(matched),
                value_usd=round(forwards[0].value_usd, 2),
                confidence=round(
                    _CONFIDENCE_CEILING
                    * (0.45 * length_score + 0.35 * thinness + 0.20 * tightness),
                    3,
                ),
                window_seconds=span,
                detail={
                    "links": len(peels),
                    "path": list(path),
                    "peel_addresses": peel_addresses,
                    "peel_ratios": [round(ratio, 4) for ratio in ratios],
                    "mean_peel_ratio": round(sum(ratios) / len(ratios), 4),
                    "entry_usd": round(forwards[0].value_usd, 2),
                    "residual_usd": round(forwards[-1].value_usd, 2),
                    "peeled_usd": round(sum(t.value_usd for t in peels), 2),
                },
            )
        )

    return matches


# ---------------------------------------------------------------------------
# 3. Cycles / U-turns
# ---------------------------------------------------------------------------


def _time_cycle(
    graph: nx.DiGraph,
    nodes: list[str],
    window_seconds: int,
) -> list[Transfer] | None:
    """Pick one transfer per hop so the loop closes forward in time.

    `nx.simple_cycles` answers a purely structural question -- these wallets
    form a ring -- and a ring that took a year to close is not a wash trade.
    Hops are chosen greedily earliest-after-the-previous, retried from a few
    different starting transfers, and the whole loop must fit in the window.
    """
    hops = list(zip(nodes, [*nodes[1:], nodes[0]], strict=True))
    first_source, first_target = hops[0]

    for start in graph[first_source][first_target]["transfers"][:_MAX_CYCLE_STARTS]:
        chosen = [start]
        for source, target in hops[1:]:
            previous = chosen[-1]
            following = next(
                (
                    candidate
                    for candidate in graph[source][target]["transfers"]
                    if candidate.timestamp >= previous.timestamp
                ),
                None,
            )
            if following is None:
                break
            chosen.append(following)
        if len(chosen) != len(hops):
            continue
        if (chosen[-1].timestamp - chosen[0].timestamp).total_seconds() <= window_seconds:
            return chosen
    return None


def detect_cycles(
    transfers: Sequence[Transfer],
    *,
    max_length: int = 6,
    window_seconds: int = 86400,
) -> list[MotifMatch]:
    """Find U-turns and wash-trading loops that close inside the window."""
    cleaned = _clean(transfers)
    if not cleaned:
        return []

    graph = _build_graph(cleaned)

    # `simple_cycles` is lazy and a dense graph holds astronomically many
    # bounded cycles, so we draw a fixed number and stop.
    raw = list(islice(nx.simple_cycles(graph, length_bound=max_length), _MAX_CYCLES))
    if len(raw) == _MAX_CYCLES:
        logger.info("motif_cycle_enumeration_capped", kept=_MAX_CYCLES, max_length=max_length)

    matches: list[MotifMatch] = []
    for cycle in raw:
        if len(cycle) < 2:
            continue
        # Rotate to the lexicographically smallest node so the same ring
        # always reports the same address ordering.
        pivot = cycle.index(min(cycle))
        nodes = cycle[pivot:] + cycle[:pivot]

        chosen = _time_cycle(graph, nodes, window_seconds)
        if chosen is None:
            continue

        values = [t.value_usd for t in chosen]
        span = _span_seconds([t.timestamp for t in chosen])

        # How much of the value actually survived the loop, how quickly it
        # closed, and how short the ring is: a tight two- or three-hop loop
        # returning nearly the same amount is the textbook U-turn.
        retention = _clamp(min(values) / max(values))
        tightness = _clamp(1.0 - span / window_seconds) if window_seconds > 0 else 0.0
        shortness = _clamp(3.0 / len(nodes))

        matches.append(
            MotifMatch(
                motif="cycle",
                addresses=tuple(nodes),
                tx_hashes=_tx_hashes(chosen),
                # The loop only truly circulated its thinnest hop; the larger
                # hops were topped up from elsewhere.
                value_usd=round(min(values), 2),
                confidence=round(
                    _CONFIDENCE_CEILING * (0.40 * retention + 0.35 * tightness + 0.25 * shortness),
                    3,
                ),
                window_seconds=span,
                detail={
                    "length": len(nodes),
                    "path": [*nodes, nodes[0]],
                    "hop_values_usd": [round(value, 2) for value in values],
                    "min_hop_usd": round(min(values), 2),
                    "max_hop_usd": round(max(values), 2),
                    "retention": round(retention, 4),
                },
            )
        )

    return matches


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_DETECTORS: tuple[Callable[..., list[MotifMatch]], ...] = (
    detect_fan_out_fan_in,
    detect_peel_chain,
    detect_cycles,
)


def _keyword_options(detector: Callable[..., list[MotifMatch]]) -> set[str]:
    return {
        name
        for name, parameter in inspect.signature(detector).parameters.items()
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    }


def detect_motifs(transfers: Sequence[Transfer], **kwargs: Any) -> list[MotifMatch]:
    """Run every motif detector and return the findings, most valuable first.

    Tuning arguments are routed to whichever detectors declare them, so
    `window_seconds` reaches all three while `min_mules` reaches only the fan
    detector. Ordering is by value then motif name then addresses: a report
    regenerated from the same evidence must come out byte-identical.
    """
    accepted = {detector: _keyword_options(detector) for detector in _DETECTORS}
    unknown = sorted(set(kwargs) - set().union(*accepted.values()))
    if unknown:
        raise TypeError(f"detect_motifs() got unexpected keyword argument(s): {', '.join(unknown)}")

    matches: list[MotifMatch] = []
    for detector, options in accepted.items():
        matches.extend(
            detector(transfers, **{key: value for key, value in kwargs.items() if key in options})
        )

    matches.sort(key=lambda match: (-match.value_usd, match.motif, match.addresses))
    logger.debug("motifs_detected", transfers=len(transfers), matches=len(matches))
    return matches


__all__ = [
    "MotifMatch",
    "detect_cycles",
    "detect_fan_out_fan_in",
    "detect_motifs",
    "detect_peel_chain",
]
