"""Guards the realism of the synthetic demo dataset.

`scripts/demo_dataset.py` deliberately imports nothing from `src`, so these
tests run without a database, Neo4j or application config. They are what stops
a demo scenario from regressing into the kind of data that falls apart the
moment a judge looks at it: a broken address checksum, a wallet spending money
it never received, a transaction that claims to span two chains at once, or a
block height that has nothing to do with the date on the case.
"""

import os
import sys
from decimal import Decimal

import pytest
from eth_utils import to_checksum_address

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from demo_dataset import (  # noqa: E402
    CHAINS,
    INFRASTRUCTURE,
    SYNTHETIC_MARKER,
    TOKENS,
    build_cases,
    case_summary,
    entity_catalogue,
    synthetic_address,
    validate_cases,
    wallet_activity,
)


@pytest.fixture(scope="module")
def cases():
    return build_cases()


def test_dataset_passes_its_own_validation(cases):
    assert validate_cases(cases) == []


def test_every_case_is_marked_synthetic(cases):
    for case in cases:
        assert "SYNTHETIC DEMO DATA" in case.description
        assert case.wallets and case.txs
        assert case.primary_key in case.wallet_by_key


def test_addresses_are_checksummed_and_well_formed(cases):
    for case in cases:
        for wallet in case.wallets:
            assert len(wallet.address) == 42
            assert to_checksum_address(wallet.address) == wallet.address


def test_infrastructure_addresses_are_real_and_distinct_per_chain():
    seen = set()
    for key, spec in INFRASTRUCTURE.items():
        address = str(spec["address"])
        assert address == address.lower(), f"{key} should be stored lowercase"
        assert len(address) == 42
        ident = (spec["chain"], address)
        assert ident not in seen, f"{key} duplicates another entry on {spec['chain']}"
        seen.add(ident)


def test_suspects_never_reuse_a_real_infrastructure_address(cases):
    """Criminal conduct is only ever attributed to generated addresses."""
    real = {(str(s["chain"]), str(s["address"]).lower()) for s in INFRASTRUCTURE.values()}
    for case in cases:
        for wallet in case.wallets:
            if wallet.synthetic:
                assert (wallet.chain, wallet.address.lower()) not in real


def test_transaction_hashes_look_like_transaction_hashes(cases):
    hashes = [tx.tx_hash for case in cases for tx in case.txs]
    assert len(hashes) == len(set(hashes))
    for tx_hash in hashes:
        assert len(tx_hash) == 66
        assert tx_hash.startswith("0x")
        int(tx_hash, 16)


def test_block_heights_track_the_clock(cases):
    """A hop that happens later must sit in a later block on its own chain."""
    for case in cases:
        for chain in {tx.chain for tx in case.txs}:
            on_chain = [tx for tx in case.txs if tx.chain == chain]
            for earlier, later in zip(on_chain, on_chain[1:], strict=False):
                assert earlier.timestamp <= later.timestamp
                assert earlier.block_number <= later.block_number
                # Height and time must agree to within a block, not merely
                # both increase.
                gap = (later.timestamp - earlier.timestamp).total_seconds()
                expected = gap / CHAINS[chain].block_seconds
                assert abs((later.block_number - earlier.block_number) - expected) <= 1


def test_values_are_priced_per_token_not_flat(cases):
    for case in cases:
        for tx in case.txs:
            token = TOKENS[(tx.chain, tx.token_symbol)]
            assert tx.value_units == str(int(tx.amount * 10**token.decimals))
            assert tx.value_usd == (tx.amount * token.usd).quantize(Decimal("0.01"))
            if tx.amount > 0:
                assert tx.value_usd > 0
            if token.address is None:
                assert tx.token_address is None
            else:
                assert tx.token_address == token.address


def test_transactions_carry_a_plausible_fee(cases):
    for case in cases:
        for tx in case.txs:
            assert tx.gas_used >= 21_000
            assert tx.gas_price_wei > 0
            assert Decimal("0") < tx.fee_native < Decimal("1")


def test_cross_chain_moves_are_two_transactions(cases):
    """A bridge is a deposit on one chain and a mint on the other."""
    for case in cases:
        by_key = case.wallet_by_key
        for tx in case.txs:
            assert by_key[tx.from_key].chain == by_key[tx.to_key].chain == tx.chain
        deposits = [tx for tx in case.txs if tx.method == "bridge_deposit"]
        mints = [tx for tx in case.txs if tx.method == "bridge_mint"]
        assert len(deposits) == len(mints)
        for deposit, mint in zip(deposits, mints, strict=False):
            assert mint.chain != deposit.chain
            assert mint.timestamp > deposit.timestamp


def test_graph_counters_come_from_the_seeded_transactions(cases):
    activity = wallet_activity(cases)
    counted = sum(entry.tx_count for entry in activity.values())
    # Every transaction touches exactly two wallet records.
    assert counted == 2 * sum(len(case.txs) for case in cases)
    for entry in activity.values():
        assert entry.first_seen <= entry.last_seen
        assert entry.tx_count > 0


def test_entity_catalogue_is_consistent(cases):
    records = entity_catalogue(cases)
    idents = [(r["chain"], str(r["address"]).lower()) for r in records]
    assert len(idents) == len(set(idents))
    for record in records:
        assert record["entity_type"] != "unknown"
        assert to_checksum_address(str(record["address"])) == record["address"]


def test_case_summary_reports_what_the_case_holds(cases):
    for case in cases:
        summary = case_summary(case)
        assert summary["wallet_count"] == len(case.wallets)
        assert summary["transaction_count"] == len(case.txs)
        assert summary["primary_wallet"] == case.wallet_by_key[case.primary_key].address
        assert summary["risk_score"] == float(case.wallet_by_key[case.primary_key].risk)
        assert summary["traced_flow_usd"] > 0


def test_synthetic_addresses_are_stable():
    assert synthetic_address("demo") == synthetic_address("demo")
    assert synthetic_address("demo") != synthetic_address("demo2")
    assert SYNTHETIC_MARKER == "SYNTHETIC_DEMO_DATA"
