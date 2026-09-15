"""Entity resolution / wallet clustering -- spec §2.3.

Syndicates script 500-1000 disposable burner wallets per case. Investigating
the raw wallet-to-wallet graph is hopeless: the sprawl is unreadable and every
traversal pays for addresses that are really one actor. This module collapses
them into a handful of "actor super-nodes" with a disjoint-set forest fed by
two classic attribution heuristics (multi-input co-spending, gas-payer
attribution), plus a deterministic stand-in for wallet-role prediction.

The module is pure -- no Postgres, no Neo4j, no network. It consumes flat
`Transfer` rows and returns value objects, so the heuristics can be argued
about (and defended in court) without a database in the loop, and the caller
decides whether the rows came from the graph repository, the `transactions`
table, or a provider response.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

import structlog

from .types import Transfer, normalize_address

logger = structlog.get_logger(__name__)

COSPEND = "cospend"
GAS_FUNDING = "gas_funding"


class UnionFind:
    """Disjoint-set forest with path compression and union by rank.

    Clustering is a transitive claim -- if A co-spends with B and B is gas-funded
    by C, the investigator is asserting one entity owns all three -- so the
    membership test has to stay near-constant time even when a single actor owns
    a thousand burners.
    """

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}
        self._rank: dict[str, int] = {}

    def __contains__(self, item: str) -> bool:
        """Has any heuristic actually touched this address?

        Distinct from `find()`, which happily answers for an address it has
        never seen. Callers use this to tell "unclustered" from "clustered
        alone".
        """
        return normalize_address(item) in self._parent

    def _ensure(self, item: str) -> str:
        if item not in self._parent:
            self._parent[item] = item
            self._rank[item] = 0
        return item

    def find(self, item: str) -> str:
        node = normalize_address(item)
        if node not in self._parent:
            # Querying is never a mutation: an address no heuristic has merged
            # is its own trivial set, and recording it here would let a mere
            # `connected()` check invent singleton "clusters".
            return node

        root = node
        while self._parent[root] != root:
            root = self._parent[root]

        # Path compression is iterative rather than recursive on purpose: a
        # scripted peel chain can be thousands of hops deep, which is well past
        # CPython's recursion limit.
        while self._parent[node] != root:
            self._parent[node], node = root, self._parent[node]

        return root

    def union(self, a: str, b: str) -> None:
        root_a = self.find(self._ensure(normalize_address(a)))
        root_b = self.find(self._ensure(normalize_address(b)))
        if root_a == root_b:
            # Idempotent: heuristics overlap constantly (the same funder shows up
            # in several windows), and re-merging must never change the forest.
            return

        if self._rank[root_a] < self._rank[root_b]:
            root_a, root_b = root_b, root_a

        self._parent[root_b] = root_a
        if self._rank[root_a] == self._rank[root_b]:
            self._rank[root_a] += 1

    def connected(self, a: str, b: str) -> bool:
        return self.find(a) == self.find(b)

    def groups(self) -> dict[str, list[str]]:
        """Root -> sorted members, for every address this forest has seen."""
        grouped: dict[str, list[str]] = defaultdict(list)
        for item in list(self._parent):
            grouped[self.find(item)].append(item)
        return {root: sorted(members) for root, members in grouped.items()}


@dataclass(frozen=True, slots=True)
class Cluster:
    """One resolved entity: the addresses believed to share a single operator."""

    cluster_id: str
    root: str
    members: tuple[str, ...]
    heuristics: tuple[str, ...]
    member_count: int
    total_value_usd: float


@dataclass(frozen=True, slots=True)
class WalletRoleGuess:
    address: str
    role: str
    confidence: float
    signals: tuple[str, ...]


def cluster_by_cospend(transfers: Sequence[Transfer]) -> UnionFind:
    """Multi-input co-spending: same tx, two or more signing addresses.

    In UTXO chains spending several inputs in one transaction proves the spender
    held every input key. In account chains the same shape appears when a batcher
    or multicall contract moves funds from several addresses inside one tx hash.
    Either way, co-signing is the strongest common-ownership signal available
    without off-chain intelligence.

    Only addresses actually merged by this heuristic enter the returned forest,
    so membership doubles as "this heuristic had something to say".
    """
    uf = UnionFind()

    senders_by_tx: dict[str, set[str]] = defaultdict(set)
    for transfer in transfers:
        senders_by_tx[transfer.tx_hash].add(transfer.from_address)

    for senders in senders_by_tx.values():
        if len(senders) < 2:
            continue
        # Anchor on the lowest address so the merge order (and therefore the
        # resulting root) does not depend on set iteration order.
        anchor, *rest = sorted(senders)
        for other in rest:
            uf.union(anchor, other)

    return uf


def cluster_by_gas_funding(
    transfers: Sequence[Transfer],
    *,
    window_seconds: int = 3600,
    min_children: int = 3,
    max_funding_usd: float = 50.0,
) -> UnionFind:
    """Gas-payer attribution: one parent seeding a burst of fresh burners.

    A deployment script funds each newly generated address with just enough gas
    to move once. The tell is the combination -- many *first-ever* receipts, all
    small, all from one payer, all inside one window. Each guard matters:

    * first-ever receipt: an ordinary payment to an established wallet says
      nothing about ownership, so only an address's opening balance counts;
    * small value: gas top-ups are dust next to the laundered principal;
    * burst window: an exchange hot wallet also pays many addresses, but spread
      across days rather than minutes;
    * min_children: two addresses is a coincidence, a dozen is a script.
    """
    uf = UnionFind()

    ordered = sorted(transfers, key=lambda t: (t.timestamp, t.tx_hash))

    first_incoming: dict[str, Transfer] = {}
    first_outgoing: dict[str, datetime] = {}
    for transfer in ordered:
        if transfer.to_address not in first_incoming:
            first_incoming[transfer.to_address] = transfer
        if transfer.from_address not in first_outgoing:
            first_outgoing[transfer.from_address] = transfer.timestamp

    fundings: dict[str, list[Transfer]] = defaultdict(list)
    for child, opening in first_incoming.items():
        if opening.from_address == child:
            continue
        if opening.value_usd > max_funding_usd:
            continue
        # Spending before its first visible receipt means the address was funded
        # outside this dataset -- it is not fresh, and the "opening" transfer we
        # can see is just an ordinary payment.
        spent_at = first_outgoing.get(child)
        if spent_at is not None and spent_at < opening.timestamp:
            continue
        fundings[opening.from_address].append(opening)

    for parent, events in fundings.items():
        events.sort(key=lambda t: (t.timestamp, t.tx_hash))

        left = 0
        attributed = 0
        for right, event in enumerate(events):
            while (event.timestamp - events[left].timestamp).total_seconds() > window_seconds:
                left += 1
            if right - left + 1 < min_children:
                continue
            # Everything still inside the qualifying window belongs to the
            # parent; `attributed` stops us re-walking children already merged
            # by an earlier (overlapping) window.
            for funded in events[max(left, attributed) : right + 1]:
                uf.union(parent, funded.to_address)
            attributed = right + 1

    return uf


def build_clusters(
    transfers: Sequence[Transfer],
    *,
    cospend: bool = True,
    gas_funding: bool = True,
    window_seconds: int = 3600,
    min_cluster_size: int = 2,
) -> list[Cluster]:
    """Merge every enabled heuristic into one forest and report the entities.

    Clusters come back sorted by value because that is the triage order an
    investigator works in: the super-node that moved the most money is the one
    worth a production order.
    """
    if not transfers:
        return []

    forests: dict[str, UnionFind] = {}
    if cospend:
        forests[COSPEND] = cluster_by_cospend(transfers)
    if gas_funding:
        forests[GAS_FUNDING] = cluster_by_gas_funding(transfers, window_seconds=window_seconds)

    merged = UnionFind()
    for forest in forests.values():
        for root, members in forest.groups().items():
            for member in members:
                merged.union(root, member)

    grouped = merged.groups()

    # Value moved by a cluster counts each transfer once even when both ends are
    # insiders: internal shuffling between an actor's own burners is not new
    # money, and double counting it would inflate the triage ranking.
    totals: dict[str, float] = defaultdict(float)
    for transfer in transfers:
        endpoints = {
            merged.find(address)
            for address in (transfer.from_address, transfer.to_address)
            if address in merged
        }
        for root in endpoints:
            totals[root] += transfer.value_usd

    clusters: list[Cluster] = []
    for root, members in grouped.items():
        if len(members) < min_cluster_size:
            continue
        contributing = tuple(
            sorted(name for name, forest in forests.items() if any(m in forest for m in members))
        )
        clusters.append(
            Cluster(
                # Derived from the lowest member address rather than a uuid: the
                # same evidence re-run months later must produce the same cluster
                # id, or nothing in a report can be cross-referenced.
                cluster_id=f"cluster:{members[0]}",
                root=root,
                members=tuple(members),
                heuristics=contributing,
                member_count=len(members),
                total_value_usd=totals.get(root, 0.0),
            )
        )

    clusters.sort(key=lambda c: (-c.total_value_usd, c.cluster_id))

    logger.debug(
        "clusters_built",
        transfer_count=len(transfers),
        cluster_count=len(clusters),
        heuristics=sorted(forests),
    )
    return clusters


# ponytail: deterministic heuristic, swap for the T-GNN when labelled training data exists
def classify_wallet_role(transfers: Sequence[Transfer], address: str) -> WalletRoleGuess:
    """Guess what job an address does inside the flow.

    The roadmap (§2.5) wants EvolveGCN probabilities here, but a T-GNN needs
    labelled Indian casework that does not exist yet. These rules use the same
    features the network would consume -- in/out degree, fan-in vs fan-out,
    hold time, value velocity, round-trip counterparties -- so the feature
    extraction is already exercised and the output shape (role + confidence +
    the signals behind it) will not change when the model lands. Every signal is
    reported so an analyst can disagree with the label on the evidence.
    """
    target = normalize_address(address)

    incoming = [t for t in transfers if t.to_address == target and t.from_address != target]
    outgoing = [t for t in transfers if t.from_address == target and t.to_address != target]

    if not incoming and not outgoing:
        return WalletRoleGuess(address=target, role="unknown", confidence=0.0, signals=())

    senders = {t.from_address for t in incoming}
    receivers = {t.to_address for t in outgoing}
    in_degree, out_degree = len(senders), len(receivers)
    value_in = sum(t.value_usd for t in incoming)
    value_out = sum(t.value_usd for t in outgoing)

    # Fraction of received value pushed straight back out: ~1.0 is a conduit,
    # ~0.0 is a destination.
    forwarded = value_out / value_in if value_in > 0 else 0.0

    moments = [t.timestamp for t in incoming + outgoing]
    active_seconds = (max(moments) - min(moments)).total_seconds()
    hold_seconds = _hold_seconds(incoming, outgoing)
    velocity = value_out / (active_seconds / 3600) if active_seconds > 0 else value_out
    round_trip = senders & receivers

    signals = [
        f"in_degree={in_degree}",
        f"out_degree={out_degree}",
        f"forwarded_ratio={forwarded:.2f}",
        f"value_in_usd={value_in:.2f}",
        f"velocity_usd_per_hour={velocity:.2f}",
    ]
    if hold_seconds is not None:
        signals.append(f"hold_seconds={int(hold_seconds)}")
    if round_trip:
        signals.append(f"round_trip_counterparties={len(round_trip)}")

    # Ordered most-specific first: a shape that satisfies two rules is reported
    # as the rarer, more actionable one.
    if in_degree >= 5 and out_degree >= 5:
        # Money in from a crowd and out to a different crowd, with no lasting
        # balance: the shape of a tumbler or a chain-hopping service.
        signals.append("fan_in_and_fan_out")
        return WalletRoleGuess(
            address=target,
            role="mixer",
            confidence=_confidence(0.55, min(in_degree, out_degree) / 40, len(round_trip) / 20),
            signals=tuple(signals),
        )

    if in_degree >= 3 and out_degree == 1 and forwarded >= 0.7:
        # Many payers, one sink, nothing retained: the classic per-user deposit
        # address sweeping into an exchange hot wallet.
        signals.append("sweeps_to_single_sink")
        return WalletRoleGuess(
            address=target,
            role="exchange_deposit",
            confidence=_confidence(0.55, in_degree / 40, forwarded / 10),
            signals=tuple(signals),
        )

    if out_degree >= 5 and out_degree >= 3 * max(in_degree, 1):
        signals.append("fan_out")
        return WalletRoleGuess(
            address=target,
            role="distributor",
            confidence=_confidence(0.55, out_degree / 50, forwarded / 10),
            signals=tuple(signals),
        )

    if (
        incoming
        and outgoing
        and out_degree <= 3
        and forwarded >= 0.7
        and hold_seconds is not None
        and hold_seconds <= 86400
    ):
        # Received and relayed almost the whole amount within a day: a rented
        # pass-through account, the layer that hides the real beneficiary.
        signals.append("pass_through")
        return WalletRoleGuess(
            address=target,
            role="mule",
            confidence=_confidence(0.5, forwarded / 5, (86400 - hold_seconds) / 864000),
            signals=tuple(signals),
        )

    if incoming and forwarded < 0.3:
        signals.append("retains_balance")
        return WalletRoleGuess(
            address=target,
            role="holder",
            confidence=_confidence(0.5, (0.3 - forwarded), 0.0),
            signals=tuple(signals),
        )

    return WalletRoleGuess(address=target, role="unknown", confidence=0.2, signals=tuple(signals))


def _hold_seconds(incoming: Sequence[Transfer], outgoing: Sequence[Transfer]) -> float | None:
    """Seconds between first receipt and the first spend that follows it.

    Spends before the first visible receipt are ignored: they were funded by
    history this dataset does not contain, so they say nothing about how long
    this wallet sits on money.
    """
    if not incoming or not outgoing:
        return None

    first_in = min(t.timestamp for t in incoming)
    later_spends = [t.timestamp for t in outgoing if t.timestamp >= first_in]
    if not later_spends:
        return None
    return (min(later_spends) - first_in).total_seconds()


def _confidence(base: float, *boosts: float) -> float:
    return round(min(1.0, max(0.0, base + sum(max(0.0, b) for b in boosts))), 2)


__all__ = [
    "COSPEND",
    "GAS_FUNDING",
    "Cluster",
    "UnionFind",
    "WalletRoleGuess",
    "build_clusters",
    "classify_wallet_role",
    "cluster_by_cospend",
    "cluster_by_gas_funding",
]
