"""Tests for the entity-resolution / wallet-clustering engine (spec §2.3).

Pure unit tests: the engine touches no database, no Neo4j and no network, so
these build `Transfer` rows in memory and assert on the forensic claims the
heuristics make -- especially the guards that stop an innocent wallet being
attributed to a syndicate.
"""

from datetime import UTC, datetime, timedelta

from src.analytics.clustering_engine import (
    COSPEND,
    GAS_FUNDING,
    UnionFind,
    build_clusters,
    classify_wallet_role,
    cluster_by_cospend,
    cluster_by_gas_funding,
)
from src.analytics.types import Transfer

T0 = datetime(2024, 3, 1, 12, 0, tzinfo=UTC)


def addr(tag: str) -> str:
    """Deterministic 20-byte-shaped address so lexical ordering is predictable."""
    return "0x" + tag.rjust(40, "0")


def transfer(
    tx: str,
    sender: str,
    receiver: str,
    value_usd: float = 10.0,
    at: datetime | None = None,
) -> Transfer:
    return Transfer(
        tx_hash=tx,
        from_address=sender,
        to_address=receiver,
        value_usd=value_usd,
        timestamp=at or T0,
    )


def test_unionfind_path_compression_and_union_by_rank() -> None:
    uf = UnionFind()

    # Build a deliberately deep chain the way a naive implementation would.
    uf.union("a", "b")  # rank(a) = 1
    uf.union("c", "d")  # rank(c) = 1
    uf.union("a", "c")  # equal ranks -> a wins, rank(a) = 2

    root = uf.find("d")
    assert root == "a"
    assert uf._rank["a"] == 2
    # Union by rank hangs the smaller tree off the larger one, never the reverse.
    assert uf._rank["c"] == 1

    # After find(), every node on the path points straight at the root.
    assert uf._parent["d"] == "a"
    assert uf._parent["c"] == "a"
    assert uf.connected("b", "d")


def test_unionfind_unions_are_idempotent_and_groups_are_sorted() -> None:
    uf = UnionFind()
    uf.union("b", "a")
    parents_after_first = dict(uf._parent)
    ranks_after_first = dict(uf._rank)

    for _ in range(5):
        uf.union("a", "b")
        uf.union("b", "a")

    assert uf._parent == parents_after_first
    assert uf._rank == ranks_after_first
    assert uf.groups() == {uf.find("a"): ["a", "b"]}
    assert not uf.connected("a", "z")


def test_cospend_merges_two_inputs_of_one_transaction() -> None:
    a, b = addr("a1"), addr("b1")
    uf = cluster_by_cospend(
        [
            transfer("0xtx1", a, addr("dest"), 500.0),
            transfer("0xtx1", b, addr("dest"), 250.0),
        ]
    )

    assert uf.connected(a, b)
    assert uf.groups() == {uf.find(a): sorted([a, b])}


def test_separate_transactions_with_unrelated_inputs_stay_separate() -> None:
    a, b = addr("a1"), addr("b1")
    uf = cluster_by_cospend(
        [
            transfer("0xtx1", a, addr("dest")),
            transfer("0xtx2", b, addr("dest")),
        ]
    )

    # Paying the same counterparty in two separate transactions proves nothing
    # about common ownership.
    assert not uf.connected(a, b)
    assert uf.groups() == {}


def test_gas_funding_clusters_five_burner_children_under_the_funder() -> None:
    funder = addr("f1")
    children = [addr(f"c{i}") for i in range(5)]

    transfers = [
        transfer(f"0xgas{i}", funder, child, 12.0, T0 + timedelta(minutes=i))
        for i, child in enumerate(children)
    ]

    uf = cluster_by_gas_funding(transfers)

    assert all(uf.connected(funder, child) for child in children)
    assert uf.groups() == {uf.find(funder): sorted([funder, *children])}


def test_large_payment_to_established_wallet_does_not_cluster() -> None:
    funder = addr("f1")
    burners = [addr(f"c{i}") for i in range(3)]
    established = addr("e1")
    counterparty = addr("d1")

    transfers = [
        # The established wallet has its own history well before the funder
        # ever touches it.
        transfer("0xold1", counterparty, established, 400.0, T0 - timedelta(days=30)),
        transfer("0xold2", established, counterparty, 120.0, T0 - timedelta(days=20)),
    ]
    transfers += [
        transfer(f"0xgas{i}", funder, burner, 9.0, T0 + timedelta(minutes=i))
        for i, burner in enumerate(burners)
    ]
    # Same funder, same window -- but a real payment to a wallet that already
    # existed, and far above any plausible gas top-up.
    transfers.append(transfer("0xpay", funder, established, 25_000.0, T0 + timedelta(minutes=3)))

    uf = cluster_by_gas_funding(transfers)

    assert all(uf.connected(funder, burner) for burner in burners)
    assert not uf.connected(funder, established)
    assert established not in uf


def test_transfers_outside_the_window_do_not_cluster() -> None:
    funder = addr("f1")
    inside = [addr(f"c{i}") for i in range(3)]
    stragglers = [addr(f"d{i}") for i in range(2)]

    transfers = [
        transfer(f"0xgas{i}", funder, child, 8.0, T0 + timedelta(minutes=i))
        for i, child in enumerate(inside)
    ]
    # Two more fresh burners, but days later: a slow drip is an exchange paying
    # customers, not a deployment script.
    transfers += [
        transfer(f"0xlate{i}", funder, child, 8.0, T0 + timedelta(days=2 + i))
        for i, child in enumerate(stragglers)
    ]

    uf = cluster_by_gas_funding(transfers, window_seconds=3600)

    assert all(uf.connected(funder, child) for child in inside)
    assert all(child not in uf for child in stragglers)


def test_window_boundary_with_min_children_not_met() -> None:
    funder = addr("f1")
    children = [addr(f"c{i}") for i in range(3)]

    transfers = [
        transfer(f"0xgas{i}", funder, child, 5.0, T0 + timedelta(hours=3 * i))
        for i, child in enumerate(children)
    ]

    # Three fresh burners, but spread so no window ever holds min_children.
    assert cluster_by_gas_funding(transfers, min_children=3).groups() == {}


def test_build_clusters_collapses_a_thousand_burner_syndicate() -> None:
    funder = addr("f1")
    burners = [addr(f"{i:x}b") for i in range(1000)]

    transfers = [
        transfer(f"0xgas{i}", funder, burner, 4.0, T0 + timedelta(seconds=i))
        for i, burner in enumerate(burners)
    ]
    # The burners then sweep the stolen principal onward.
    transfers += [
        transfer(f"0xmove{i}", burner, addr("sink"), 900.0, T0 + timedelta(hours=2, seconds=i))
        for i, burner in enumerate(burners)
    ]

    clusters = build_clusters(transfers)

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.member_count == 1001
    assert cluster.heuristics == (GAS_FUNDING,)
    assert cluster.cluster_id == f"cluster:{min([funder, *burners])}"
    assert cluster.root in cluster.members
    # 1000 gas top-ups at $4 plus 1000 sweeps at $900.
    assert cluster.total_value_usd == 904_000.0


def test_build_clusters_respects_min_cluster_size_and_value_ordering() -> None:
    funder = addr("f1")
    burners = [addr(f"c{i}") for i in range(4)]
    cospenders = (addr("e1"), addr("e2"))

    transfers = [
        transfer(f"0xgas{i}", funder, burner, 3.0, T0 + timedelta(minutes=i))
        for i, burner in enumerate(burners)
    ]
    transfers += [
        transfer("0xmulti", cospenders[0], addr("sink"), 100.0, T0),
        transfer("0xmulti", cospenders[1], addr("sink"), 50.0, T0),
    ]

    both = build_clusters(transfers, min_cluster_size=2)
    assert len(both) == 2
    # Ranked for triage: the pair moved $150, the burner ring only $12.
    assert [c.heuristics for c in both] == [(COSPEND,), (GAS_FUNDING,)]
    assert both[0].total_value_usd > both[1].total_value_usd

    only_large = build_clusters(transfers, min_cluster_size=3)
    assert [c.member_count for c in only_large] == [5]
    assert all(c.member_count >= 3 for c in only_large)


def test_build_clusters_merges_both_heuristics_into_one_entity() -> None:
    funder = addr("f1")
    burners = [addr(f"c{i}") for i in range(3)]

    transfers = [
        transfer(f"0xgas{i}", funder, burner, 6.0, T0 + timedelta(minutes=i))
        for i, burner in enumerate(burners)
    ]
    # One of the burners later co-spends with an address the gas heuristic never
    # saw, which drags that address into the same entity.
    outsider = addr("aa")
    transfers += [
        transfer("0xmulti", burners[0], addr("sink"), 700.0, T0 + timedelta(hours=1)),
        transfer("0xmulti", outsider, addr("sink"), 300.0, T0 + timedelta(hours=1)),
    ]

    clusters = build_clusters(transfers)

    assert len(clusters) == 1
    assert clusters[0].heuristics == (COSPEND, GAS_FUNDING)
    assert outsider in clusters[0].members
    assert clusters[0].member_count == 5


def test_classify_wallet_role_distinguishes_distributor_from_mule() -> None:
    distributor = addr("d1")
    mule = addr("m1")

    fan_out = [transfer("0xin", addr("src"), distributor, 10_000.0, T0)]
    fan_out += [
        transfer(f"0xout{i}", distributor, addr(f"x{i}"), 900.0, T0 + timedelta(minutes=i + 1))
        for i in range(10)
    ]

    pass_through = [
        transfer("0xin", addr("src"), mule, 5_000.0, T0),
        transfer("0xout", mule, addr("nextho"), 4_900.0, T0 + timedelta(minutes=4)),
    ]

    distributor_guess = classify_wallet_role(fan_out, distributor)
    mule_guess = classify_wallet_role(pass_through, mule)

    assert distributor_guess.role == "distributor"
    assert mule_guess.role == "mule"
    assert distributor_guess.role != mule_guess.role
    assert 0.0 < distributor_guess.confidence <= 1.0
    assert 0.0 < mule_guess.confidence <= 1.0
    assert any(s.startswith("out_degree=10") for s in distributor_guess.signals)
    assert "pass_through" in mule_guess.signals


def test_classify_wallet_role_covers_deposit_mixer_holder_and_unknown() -> None:
    deposit = addr("de")
    deposits = [
        transfer(f"0xin{i}", addr(f"p{i}"), deposit, 500.0, T0 + timedelta(minutes=i))
        for i in range(4)
    ]
    deposits.append(transfer("0xsweep", deposit, addr("hotwal"), 1_990.0, T0 + timedelta(hours=1)))
    assert classify_wallet_role(deposits, deposit).role == "exchange_deposit"

    mixer = addr("mx")
    mixed = [
        transfer(f"0xin{i}", addr(f"p{i}"), mixer, 100.0, T0 + timedelta(minutes=i))
        for i in range(6)
    ]
    mixed += [
        transfer(f"0xout{i}", mixer, addr(f"q{i}"), 95.0, T0 + timedelta(hours=1, minutes=i))
        for i in range(6)
    ]
    assert classify_wallet_role(mixed, mixer).role == "mixer"

    holder = addr("h1")
    held = [
        transfer("0xin", addr("src"), holder, 20_000.0, T0),
        transfer("0xout", holder, addr("shop"), 100.0, T0 + timedelta(days=200)),
    ]
    assert classify_wallet_role(held, holder).role == "holder"

    silent = classify_wallet_role(held, addr("zz"))
    assert silent.role == "unknown"
    assert silent.confidence == 0.0
    assert silent.signals == ()


def test_empty_input_returns_no_clusters() -> None:
    assert build_clusters([]) == []
    assert cluster_by_cospend([]).groups() == {}
    assert cluster_by_gas_funding([]).groups() == {}
    assert classify_wallet_role([], addr("a1")).role == "unknown"
