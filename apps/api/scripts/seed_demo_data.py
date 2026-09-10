#!/usr/bin/env python3
"""
TRACE-X Demo Data Seeder

Writes the synthetic SIH 2026 demonstration dataset into PostgreSQL and Neo4j.
Every row and node it creates carries `SYNTHETIC_DEMO_DATA` in its metadata,
and re-running the seeder deletes and rebuilds only what carries that marker.

The dataset itself -- cases, wallets, flows, prices, block heights -- lives in
`demo_dataset.py`, which can be built and validated on its own:

    python scripts/demo_dataset.py

This module is the part that talks to the databases: it maps the dataset onto
the ORM models and the graph repository, and derives the investigation runs
and case reports from the transactions actually written (rather than from
random numbers, which is how a demo ends up claiming 400 transactions on a
case that holds 20).
"""

import asyncio
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Add apps/api (this script's parent's parent) to the path so `src` imports
# resolve regardless of the caller's cwd, and this script's own directory so
# `demo_dataset` resolves the same way.
API_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from demo_dataset import (
    SYNTHETIC_MARKER,
    build_dataset,
    case_summary,
    entity_catalogue,
    wallet_activity,
)
from demo_dataset import (
    Case as DemoCase,
)

from src.auth import hash_password
from src.core.config import get_settings
from src.core.database import Base
from src.graph.client import Neo4jClient
from src.graph.models import ConfidenceLevel, EntityType, GraphEntity, GraphTransaction, GraphWallet
from src.graph.repository import graph_repository
from src.models import (
    AttributionStatus,
    Case,
    CaseStatus,
    CrimeType,
    InvestigationRun,
    InvestigationStatus,
    Report,
    Transaction,
    User,
    UserRole,
    Wallet,
)

settings = get_settings()

# ============================================================
# DEMO USERS
# ============================================================

#: Password every seeded demo account shares. These are synthetic accounts in a
#: local demo database; the seeder is never run against production (it writes
#: SYNTHETIC_MARKER-tagged rows). `users.hashed_password` is NOT NULL, so a
#: value has to be supplied here or the whole seed transaction aborts.
DEMO_USER_PASSWORD = "tracex-demo-password"

DEMO_USERS = [
    {
        "email": "analyst.a@tracex.gov",
        "full_name": "Analyst A - Crypto Forensics Desk",
        "role": UserRole.ANALYST,
        "is_active": True,
    },
    {
        "email": "analyst.b@tracex.gov",
        "full_name": "Analyst B - Crypto Forensics Desk",
        "role": UserRole.ANALYST,
        "is_active": True,
    },
    {
        "email": "supervisor@tracex.gov",
        "full_name": "Supervising Officer - Cyber Crime Unit",
        "role": UserRole.SUPERVISOR,
        "is_active": True,
    },
    {
        "email": "admin@tracex.gov",
        "full_name": "System Administrator",
        "role": UserRole.ADMIN,
        "is_active": True,
    },
]

CASES: list[DemoCase] = build_dataset()


# ============================================================
# HELPERS
# ============================================================


def _case_close(case: DemoCase):
    """When the case last changed: its final transaction, or when it opened."""
    return max([case.opened_at, *(tx.timestamp for tx in case.txs)])


def _entity_type(value: str | None) -> EntityType:
    try:
        return EntityType(value) if value else EntityType.UNKNOWN
    except ValueError:
        return EntityType.UNKNOWN


def _confidence(value: str | None) -> ConfidenceLevel:
    try:
        return ConfidenceLevel(value) if value else ConfidenceLevel.UNKNOWN
    except ValueError:
        return ConfidenceLevel.UNKNOWN


def _tx_metadata(case: DemoCase, tx) -> dict:
    """Everything about a transaction that has no dedicated column.

    Gas, fee and nonce are what an analyst uses to tell a contract call from a
    plain transfer and to spot a freshly created wallet, so they are recorded
    even though the ORM model has no column for them.
    """
    metadata = {
        "source": SYNTHETIC_MARKER,
        "case_number": case.case_number,
        "gas_used": tx.gas_used,
        "gas_price_wei": str(tx.gas_price_wei),
        "gas_price_gwei": f"{Decimal(tx.gas_price_wei) / 10**9:.3f}",
        "fee_native": f"{tx.fee_native}",
        "nonce": tx.nonce,
    }
    if tx.token_transfers:
        metadata["token_transfers"] = tx.token_transfers
    if tx.note:
        metadata["analyst_note"] = tx.note
    return metadata


def _investigation_plan(case: DemoCase) -> list[tuple[str, InvestigationStatus]]:
    """Which wallets have been run through the tracer, and how far each got.

    Closed and archived cases are finished, so every run on them is COMPLETED;
    live cases have one finished run, one still going and one queued.
    """
    # Only the scenario's own actors are worth tracing. Ranking every wallet
    # would queue a run against the Tornado Cash pool or a Uniswap router
    # purely because published infrastructure carries the highest risk score.
    ranked = sorted((w for w in case.wallets if w.synthetic), key=lambda w: w.risk, reverse=True)
    keys = [case.primary_key] + [w.key for w in ranked if w.key != case.primary_key]
    if case.status in ("closed", "archived"):
        return [(key, InvestigationStatus.COMPLETED) for key in keys[:3]]
    return list(
        zip(
            keys[:3],
            [
                InvestigationStatus.COMPLETED,
                InvestigationStatus.RUNNING,
                InvestigationStatus.PENDING,
            ],
            strict=False,
        )
    )


def _result_summary(case: DemoCase, summary: dict) -> dict:
    return {
        "transactions_found": summary["transaction_count"],
        "suspicious_transactions": summary["suspicious_count"],
        "unique_addresses": summary["wallet_count"],
        "aggregate_flow_usd": round(summary["traced_flow_usd"], 2),
        "largest_transaction_usd": round(summary["largest_tx_usd"], 2),
        "mixer_transactions": summary["mixer_transactions"],
        "chains_analyzed": summary["chains"],
        "vasp_endpoints": summary["vasp_endpoints"],
        "trace_window": [summary["first_tx"], summary["last_tx"]],
        "demo": True,
    }


# ============================================================
# POSTGRES
# ============================================================


async def seed_database():
    """Seed PostgreSQL with demo data."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Re-seeding is idempotent, the same way the Neo4j half is. Without
        # this a second run dies on the users.email / cases.case_number unique
        # constraints, leaving a half-written database behind.
        #
        # Demo cases are deleted and rebuilt -- that cascades to their wallets,
        # transactions, investigation runs and reports (all ON DELETE CASCADE).
        await session.execute(
            delete(Case).where(Case.case_number.in_([c.case_number for c in CASES]))
        )
        await session.flush()

        # Demo users are *upserted*, not deleted and recreated. They are
        # referenced by rows this seeder does not own -- audit_log.actor_id
        # from any login, reports.generated_by for reports raised against
        # non-demo cases -- and neither FK cascades, so deleting the users
        # fails with a ForeignKeyViolationError. Updating in place keeps every
        # existing reference valid.
        demo_password_hash = hash_password(DEMO_USER_PASSWORD)
        demo_emails = [u["email"] for u in DEMO_USERS]
        existing_users = (
            (await session.execute(select(User).where(User.email.in_(demo_emails)))).scalars().all()
        )
        by_email = {u.email: u for u in existing_users}

        user_map = {}
        created = 0
        for udata in DEMO_USERS:
            user = by_email.get(udata["email"])
            if user is None:
                user = User(id=uuid4(), email=udata["email"])
                session.add(user)
                created += 1
            user.full_name = udata["full_name"]
            user.hashed_password = demo_password_hash
            user.role = udata["role"]
            user.is_active = udata["is_active"]
            user_map[udata["email"]] = user
        await session.flush()
        print(
            f"Seeded {len(user_map)} demo users ({created} created, {len(user_map) - created} updated)"
        )

        analyst_a = user_map["analyst.a@tracex.gov"]
        analyst_b = user_map["analyst.b@tracex.gov"]
        supervisor = user_map["supervisor@tracex.gov"]

        for index, demo_case in enumerate(CASES):
            summary = case_summary(demo_case)
            closed_at = _case_close(demo_case)
            # Live cases go to the analysts, finished ones sit with the
            # supervisor who signed them off.
            owner = (
                supervisor
                if demo_case.status in ("closed", "archived")
                else (analyst_a if index % 2 == 0 else analyst_b)
            )

            case = Case(
                id=uuid4(),
                case_number=demo_case.case_number,
                title=demo_case.title,
                crime_type=CrimeType(demo_case.crime_type),
                description=demo_case.description,
                status=CaseStatus(demo_case.status),
                assigned_to=owner.id,
                case_metadata={
                    "source": SYNTHETIC_MARKER,
                    "opened_at": demo_case.opened_at.isoformat(),
                    "chains": summary["chains"],
                    "tags": demo_case.tags,
                    "aggregate_flow_usd": round(summary["traced_flow_usd"], 2),
                    "trace_window": [summary["first_tx"], summary["last_tx"]],
                    "primary_wallet": summary["primary_wallet"],
                },
                created_at=demo_case.opened_at,
                updated_at=closed_at,
            )
            session.add(case)
            await session.flush()

            # --- wallets ---------------------------------------------------
            first_tx_hash: dict[str, str] = {}
            for tx in demo_case.txs:
                first_tx_hash.setdefault(tx.from_key, tx.tx_hash)
                first_tx_hash.setdefault(tx.to_key, tx.tx_hash)

            wallet_rows: dict[str, Wallet] = {}
            for demo_wallet in demo_case.wallets:
                row = Wallet(
                    id=uuid4(),
                    case_id=case.id,
                    address=demo_wallet.address,
                    chain=demo_wallet.chain,
                    label=demo_wallet.label[:100],
                    attribution_status=AttributionStatus(demo_wallet.attribution),
                    risk_score=demo_wallet.risk,
                    entity_name=demo_wallet.entity_name,
                    entity_type=demo_wallet.entity_type,
                    entity_confidence=demo_wallet.entity_confidence,
                    first_seen_tx_hash=first_tx_hash.get(demo_wallet.key),
                    wallet_metadata={
                        "source": SYNTHETIC_MARKER,
                        "role": "infrastructure" if not demo_wallet.synthetic else "actor",
                        "note": demo_wallet.note,
                    },
                    created_at=demo_case.opened_at,
                    updated_at=closed_at,
                )
                session.add(row)
                wallet_rows[demo_wallet.key] = row
            await session.flush()

            # --- transactions ----------------------------------------------
            #
            # One row per on-chain transaction, owned by the sending wallet. A
            # mirrored row for the receiving wallet reusing the same tx_hash
            # would violate the unique ix_transactions_tx_hash index (a hash is
            # globally unique on-chain). The receiving side is reachable via
            # `to_address`, and the Neo4j half below models both directions
            # explicitly with SENT/RECEIVED relationships.
            for tx in demo_case.txs:
                session.add(
                    Transaction(
                        id=uuid4(),
                        wallet_id=wallet_rows[tx.from_key].id,
                        tx_hash=tx.tx_hash,
                        block_number=tx.block_number,
                        timestamp=tx.timestamp,
                        from_address=tx.from_address,
                        to_address=tx.to_address,
                        value=tx.value_units,
                        value_usd=tx.value_usd,
                        token_address=tx.token_address,
                        token_symbol=tx.token_symbol,
                        method=tx.method,
                        is_suspicious=tx.is_suspicious,
                        transaction_metadata=_tx_metadata(demo_case, tx),
                        created_at=tx.timestamp,
                        updated_at=tx.timestamp,
                    )
                )

            # --- investigation runs -----------------------------------------
            started = demo_case.opened_at + timedelta(minutes=25)
            for wallet_key, status in _investigation_plan(demo_case):
                duration = timedelta(minutes=3 + len(demo_case.txs) // 4)
                completed = started + duration if status == InvestigationStatus.COMPLETED else None
                session.add(
                    InvestigationRun(
                        id=uuid4(),
                        case_id=case.id,
                        wallet_id=wallet_rows[wallet_key].id,
                        status=status,
                        started_at=started,
                        completed_at=completed,
                        config={
                            "trace_depth": 6,
                            "max_transactions": 1000,
                            "chains": summary["chains"],
                            "include_exchange_sweeps": True,
                            "demo": True,
                        },
                        result_summary=_result_summary(demo_case, summary)
                        if status == InvestigationStatus.COMPLETED
                        else None,
                        created_at=started,
                        updated_at=completed or started,
                    )
                )
                started += duration + timedelta(minutes=17)

            # --- report ------------------------------------------------------
            if demo_case.status in ("closed", "in_progress"):
                risks = [w.risk for w in demo_case.wallets]
                report_at = closed_at + timedelta(hours=6)
                session.add(
                    Report(
                        id=uuid4(),
                        case_id=case.id,
                        title=f"{demo_case.title} - Investigation Report",
                        summary=(
                            f"{summary['transaction_count']} transactions across "
                            f"{len(summary['chains'])} chain(s) and {summary['wallet_count']} wallets, "
                            f"USD {summary['traced_flow_usd']:,.0f} of aggregate traced flow, "
                            f"{summary['mixer_transactions']} mixer interaction(s), "
                            f"{len(summary['vasp_endpoints'])} attributed exchange endpoint(s)."
                        ),
                        findings={
                            "executive_summary": demo_case.description,
                            "key_findings": demo_case.findings,
                            "vasp_endpoints": summary["vasp_endpoints"],
                            "trace_window": [summary["first_tx"], summary["last_tx"]],
                        },
                        risk_assessment={
                            "overall_risk": "HIGH" if max(risks) >= 85 else "MEDIUM",
                            "highest_score": float(max(risks)),
                            "average_score": float(round(sum(risks) / len(risks), 2)),
                            "critical_wallets": sum(1 for r in risks if r >= 85),
                            "mixer_exposure": summary["mixer_transactions"] > 0,
                        },
                        generated_by=owner.id,
                        format="pdf",
                        created_at=report_at,
                        updated_at=report_at,
                    )
                )

            print(
                f"Created case {demo_case.case_number}: {summary['wallet_count']} wallets, "
                f"{summary['transaction_count']} transactions, USD {summary['traced_flow_usd']:,.0f} traced"
            )

        await session.commit()
        print("Database seeding completed!")

    await engine.dispose()


# ============================================================
# NEO4J
# ============================================================


async def seed_neo4j():
    """Seed Neo4j with the same flows, as a graph."""
    await Neo4jClient.initialize()

    async with Neo4jClient.session() as session:
        # Clear existing demo data so re-running the seeder is idempotent.
        # `metadata` is stored as a JSON *string* (Neo4j property values can
        # only be primitives or arrays, so a nested map cannot be written at
        # all -- see _dump_metadata in src/graph/repository.py). A
        # `n.metadata.source = $marker` map access would raise a
        # CypherTypeError and delete nothing; substring-match the serialized
        # marker instead.
        await session.run(
            "MATCH (n) WHERE n.metadata IS NOT NULL AND n.metadata CONTAINS $marker "
            "DETACH DELETE n",
            marker=SYNTHETIC_MARKER,
        )

    activity = wallet_activity(CASES)

    # --- wallets ---------------------------------------------------------
    #
    # One node per (chain, address), not per case row: an address that appears
    # in two investigations is one wallet on the graph, and merging them is
    # what lets an analyst pivot from one case to another. Counters come from
    # `wallet_activity`, so they match the edges actually written.
    merged: dict[tuple[str, str], dict] = {}
    for case in CASES:
        for wallet in case.wallets:
            ident = (wallet.chain, wallet.address)
            current = merged.get(ident)
            if current is None or wallet.risk > current["risk"]:
                merged[ident] = {
                    "wallet": wallet,
                    "risk": wallet.risk,
                    "cases": (current or {}).get("cases", []),
                }
            merged[ident]["cases"] = sorted({*merged[ident].get("cases", []), case.case_number})

    for (chain, address), entry in merged.items():
        wallet = entry["wallet"]
        stats = activity[(chain, address)]
        await graph_repository.upsert_wallet(
            GraphWallet(
                address=address,
                chain=chain,
                label=wallet.label,
                risk_score=float(entry["risk"]),
                first_seen=stats.first_seen,
                last_seen=stats.last_seen,
                total_sent=int(stats.sent_usd),
                total_received=int(stats.received_usd),
                tx_count=stats.tx_count,
                entity_name=wallet.entity_name,
                entity_type=_entity_type(wallet.entity_type),
                entity_confidence=_confidence(wallet.entity_confidence),
                metadata={
                    "source": SYNTHETIC_MARKER,
                    "cases": entry["cases"],
                    "volume_unit": "usd",
                    "role": "infrastructure" if not wallet.synthetic else "actor",
                },
            )
        )

    # --- entities ---------------------------------------------------------
    for record in entity_catalogue(CASES):
        await graph_repository.upsert_entity(
            GraphEntity(
                name=str(record["name"]),
                entity_type=_entity_type(str(record["entity_type"])),
                address=str(record["address"]),
                chain=str(record["chain"]),
                confidence=_confidence(str(record["confidence"])),
                source=str(record["source"]),
                tags=list(record["tags"]),  # type: ignore[arg-type]
                metadata={"source": SYNTHETIC_MARKER},
            )
        )

    # Link every attributed wallet to the entity node sitting at the same
    # address. `entity_catalogue` only emits a node for a typed entity, so
    # wallets whose entity_type is still "unknown" are skipped rather than
    # issuing a MATCH that silently finds nothing.
    for (chain, address), entry in merged.items():
        wallet = entry["wallet"]
        if wallet.entity_name and wallet.entity_type != "unknown":
            await graph_repository.link_wallet_entity(address, chain, address)

    # --- transactions -----------------------------------------------------
    for case in CASES:
        for tx in case.txs:
            await graph_repository.upsert_transaction(
                GraphTransaction(
                    tx_hash=tx.tx_hash,
                    chain=tx.chain,
                    block_number=tx.block_number,
                    timestamp=tx.timestamp,
                    from_address=tx.from_address,
                    to_address=tx.to_address,
                    value=tx.value_units,
                    value_usd=float(tx.value_usd),
                    token_address=tx.token_address,
                    token_symbol=tx.token_symbol,
                    method=tx.method,
                    gas_used=tx.gas_used,
                    gas_price=str(tx.gas_price_wei),
                    is_suspicious=tx.is_suspicious,
                    metadata={
                        "source": SYNTHETIC_MARKER,
                        "case_number": case.case_number,
                        "fee_native": f"{tx.fee_native}",
                        "nonce": tx.nonce,
                        "note": tx.note,
                    },
                )
            )
            # Both endpoints are on the transaction's own chain (cross-chain
            # movement is modelled as a deposit tx plus a separate mint tx),
            # so both links match.
            await graph_repository.link_wallet_transaction(
                tx.from_address, tx.chain, tx.tx_hash, "sent"
            )
            await graph_repository.link_wallet_transaction(
                tx.to_address, tx.chain, tx.tx_hash, "received"
            )

    print(
        f"Neo4j seeding completed: {len(merged)} wallets, "
        f"{sum(len(c.txs) for c in CASES)} transactions, {len(entity_catalogue(CASES))} entities"
    )


async def main():
    print("=" * 60)
    print("TRACE-X Demo Data Seeder")
    print("=" * 60)
    print(f"Seeding SYNTHETIC demo data for SIH 2026 ({len(CASES)} cases)")
    print("=" * 60)

    await seed_database()
    await seed_neo4j()

    print("=" * 60)
    print("All demo data seeded successfully!")
    print(f"Demo logins: {', '.join(u['email'] for u in DEMO_USERS)} / {DEMO_USER_PASSWORD}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
