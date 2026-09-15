"""Forensic analytics routes.

These endpoints expose the pure engines in `src/analytics/` over a case's
stored transaction set: taint propagation, entity clustering, laundering motif
mining, flow analysis, cross-chain bridge matching, P2P fiat correlation and
the Section 63 BSA evidence certificate.

The engines never touch a database -- this module is the only place that turns
`transactions` rows into the flat `Transfer` records they consume, so the same
engines can later be fed from Neo4j or straight from a provider response.
"""

import io
from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.analytics.clustering_engine import build_clusters, classify_wallet_role
from src.analytics.correlation_engine import correlate_fiat_to_chain, match_bridge_transfers
from src.analytics.flow_engine import flow_weighted_path, max_flow_min_cut
from src.analytics.motif_engine import detect_motifs
from src.analytics.taint_engine import propagate_fifo, propagate_haircut, taint_summary
from src.analytics.types import FiatPayment, Transfer
from src.core import NotFoundError, get_session
from src.models import Case, Transaction, Wallet
from src.reports.evidence_certificate import (
    EvidenceRecord,
    build_certificate,
    generate_certificate_pdf,
    verify_certificate,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/forensics", tags=["forensics"])

# A case's whole transaction set is loaded into memory for the engines. Real
# investigations top out in the low thousands of rows; the cap stops a runaway
# case from pinning the worker.
MAX_TRANSFERS = 20000


async def _require_case(session: AsyncSession, case_id: UUID) -> Case:
    case = await session.get(Case, case_id)
    if not case:
        raise NotFoundError("Case", str(case_id))
    return case


async def _load_transfers(
    session: AsyncSession,
    case_id: UUID,
    *,
    chain: str | None = None,
    limit: int = MAX_TRANSFERS,
) -> list[Transfer]:
    """Every transaction recorded against the case, as engine input.

    Rows with no USD valuation are dropped rather than defaulted to 0: a
    zero-value edge would silently dilute every taint ratio and flow capacity
    computed downstream.
    """
    stmt = (
        select(Transaction, Wallet.chain)
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .where(Wallet.case_id == case_id)
        .order_by(Transaction.timestamp.asc())
        .limit(limit)
    )
    if chain:
        stmt = stmt.where(Wallet.chain == chain)

    rows = (await session.execute(stmt)).all()

    transfers: list[Transfer] = []
    seen: set[str] = set()
    for tx, wallet_chain in rows:
        # One transaction is stored once per wallet it touches, so the same
        # tx_hash can come back twice (sender side and receiver side). Feeding
        # both to the engines would double-count the money moved.
        if tx.tx_hash in seen:
            continue
        seen.add(tx.tx_hash)
        if tx.value_usd is None:
            continue
        value_usd = float(tx.value_usd)
        if value_usd <= 0:
            continue
        transfers.append(
            Transfer(
                tx_hash=tx.tx_hash,
                from_address=tx.from_address,
                to_address=tx.to_address,
                value_usd=value_usd,
                timestamp=tx.timestamp,
                chain=wallet_chain,
                asset=tx.token_symbol or "NATIVE",
                block_number=tx.block_number,
            )
        )
    return transfers


async def _default_sources(
    session: AsyncSession, case_id: UUID, transfers: list[Transfer], top_n: int = 3
) -> dict[str, float]:
    """Seed taint from the case's highest-risk wallets when the caller gives none.

    The alternative -- seeding every wallet -- taints the whole graph at 100%
    and tells an investigator nothing.
    """
    stmt = (
        select(Wallet)
        .where(Wallet.case_id == case_id)
        .order_by(Wallet.risk_score.desc())
        .limit(top_n)
    )
    wallets = (await session.execute(stmt)).scalars().all()

    sources: dict[str, float] = {}
    for wallet in wallets:
        address = wallet.address.lower() if wallet.address.startswith("0x") else wallet.address
        outgoing = sum(t.value_usd for t in transfers if t.from_address == address)
        incoming = sum(t.value_usd for t in transfers if t.to_address == address)
        seeded = outgoing or incoming
        if seeded > 0:
            sources[address] = seeded
    return sources


class TaintRequest(BaseModel):
    model: str = Field("haircut", pattern="^(haircut|fifo)$")
    max_hops: int = Field(6, ge=1, le=12)
    sources: dict[str, float] | None = None
    top_n: int = Field(20, ge=1, le=200)
    min_taint_usd: float = Field(1.0, ge=0.0)


class ClusterRequest(BaseModel):
    cospend: bool = True
    gas_funding: bool = True
    window_seconds: int = Field(3600, ge=60, le=86400)
    min_cluster_size: int = Field(2, ge=2, le=50)


class MotifRequest(BaseModel):
    window_seconds: int = Field(1800, ge=60, le=604800)
    min_mules: int = Field(3, ge=2, le=50)
    max_cycle_length: int = Field(6, ge=3, le=10)


class FlowRequest(BaseModel):
    source: str
    target: str
    max_hops: int = Field(8, ge=1, le=15)


class BridgeRequest(BaseModel):
    window_seconds: int = Field(3600, ge=60, le=86400)
    value_tolerance_pct: float = Field(2.0, ge=0.1, le=50.0)
    bridge_addresses: list[str] | None = None


class FiatPaymentInput(BaseModel):
    reference_id: str
    payer_account: str
    payee_account: str
    amount_inr: float
    timestamp: datetime
    rail: str = "UPI"


class P2PRequest(BaseModel):
    payments: list[FiatPaymentInput]
    window_seconds: int = Field(600, ge=60, le=7200)
    usd_inr_rate: float = Field(83.0, gt=0)
    amount_tolerance_pct: float = Field(5.0, ge=0.1, le=50.0)


class EvidenceCertificateRequest(BaseModel):
    investigating_officer: str = Field(..., min_length=2, max_length=200)
    designation: str | None = None
    place: str | None = None


@router.post(
    "/cases/{case_id}/taint",
    summary="Propagate taint across a case",
    description=(
        "Propagate illicit-fund taint across the case's transaction graph using either the "
        "pro-rata haircut model or the FIFO poison model. Returns the tainted USD amount and "
        "taint percentage reaching each downstream address."
    ),
)
async def run_taint_analysis(
    case_id: UUID,
    request: TaintRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _require_case(session, case_id)
    transfers = await _load_transfers(session, case_id)
    sources = request.sources or await _default_sources(session, case_id, transfers)

    propagate = propagate_haircut if request.model == "haircut" else propagate_fifo
    results = propagate(
        transfers,
        sources,
        max_hops=request.max_hops,
        min_taint_usd=request.min_taint_usd,
    )

    return {
        "case_id": str(case_id),
        "model": request.model,
        "sources": sources,
        "transfer_count": len(transfers),
        "tainted_address_count": len(results),
        "total_tainted_usd": round(sum(r.tainted_value_usd for r in results.values()), 2),
        "results": taint_summary(results, top_n=request.top_n),
    }


@router.post(
    "/cases/{case_id}/clusters",
    summary="Cluster a case's wallets into entities",
    description=(
        "Collapse burner wallets into actor super-nodes using Union-Find over the multi-input "
        "co-spending and gas-funding heuristics."
    ),
)
async def run_clustering(
    case_id: UUID,
    request: ClusterRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _require_case(session, case_id)
    transfers = await _load_transfers(session, case_id)

    clusters = build_clusters(
        transfers,
        cospend=request.cospend,
        gas_funding=request.gas_funding,
        window_seconds=request.window_seconds,
        min_cluster_size=request.min_cluster_size,
    )

    addresses = {t.from_address for t in transfers} | {t.to_address for t in transfers}
    return {
        "case_id": str(case_id),
        "transfer_count": len(transfers),
        "address_count": len(addresses),
        "cluster_count": len(clusters),
        "clustered_address_count": sum(c.member_count for c in clusters),
        "clusters": [
            {
                "cluster_id": c.cluster_id,
                "root": c.root,
                "members": list(c.members),
                "member_count": c.member_count,
                "heuristics": list(c.heuristics),
                "total_value_usd": round(c.total_value_usd, 2),
            }
            for c in clusters
        ],
    }


@router.get(
    "/cases/{case_id}/wallet-role",
    summary="Classify a wallet's role in a case",
    description=(
        "Heuristic role classification (mule, exchange deposit, mixer, distributor, holder) "
        "derived from the wallet's flow behaviour within the case."
    ),
)
async def get_wallet_role(
    case_id: UUID,
    address: str = Query(..., min_length=4),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _require_case(session, case_id)
    transfers = await _load_transfers(session, case_id)
    guess = classify_wallet_role(transfers, address)
    return {
        "case_id": str(case_id),
        "address": guess.address,
        "role": guess.role,
        "confidence": round(guess.confidence, 4),
        "signals": list(guess.signals),
    }


@router.post(
    "/cases/{case_id}/motifs",
    summary="Mine laundering motifs",
    description=(
        "Detect smurfing fan-out/fan-in (VF2 subgraph isomorphism under a temporal window), "
        "peel chains and cyclical wash trades across the case's transaction graph."
    ),
)
async def run_motif_mining(
    case_id: UUID,
    request: MotifRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _require_case(session, case_id)
    transfers = await _load_transfers(session, case_id)

    matches = detect_motifs(
        transfers,
        window_seconds=request.window_seconds,
        min_mules=request.min_mules,
        max_length=request.max_cycle_length,
    )

    counts: dict[str, int] = {}
    for match in matches:
        counts[match.motif] = counts.get(match.motif, 0) + 1

    return {
        "case_id": str(case_id),
        "transfer_count": len(transfers),
        "match_count": len(matches),
        "counts_by_motif": counts,
        "matches": [
            {
                "motif": m.motif,
                "addresses": list(m.addresses),
                "tx_hashes": list(m.tx_hashes),
                "value_usd": round(m.value_usd, 2),
                "confidence": round(m.confidence, 4),
                "window_seconds": m.window_seconds,
                "detail": m.detail,
            }
            for m in matches
        ],
    }


@router.post(
    "/cases/{case_id}/flow",
    summary="Flow-weighted path and max-flow between two addresses",
    description=(
        "Value-weighted shortest path (high-value edges are cheap to traverse, so the main "
        "laundering corridor wins over a low-value decoy hop) plus the max-flow / min-cut "
        "between the two addresses. The min-cut edges are the set to freeze."
    ),
)
async def run_flow_analysis(
    case_id: UUID,
    request: FlowRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _require_case(session, case_id)
    transfers = await _load_transfers(session, case_id)

    path = flow_weighted_path(transfers, request.source, request.target, max_hops=request.max_hops)
    flow = max_flow_min_cut(transfers, request.source, request.target)

    return {
        "case_id": str(case_id),
        "source": request.source,
        "target": request.target,
        "transfer_count": len(transfers),
        "path": None
        if path is None
        else {
            "nodes": list(path.nodes),
            "edges": list(path.edges),
            "total_value_usd": round(path.total_value_usd, 2),
            "hops": path.hops,
            "weight": path.weight,
        },
        "max_flow_usd": round(flow.max_flow_usd, 2),
        "bottleneck_usd": round(flow.bottleneck_usd, 2),
        "min_cut_edges": [list(edge) for edge in flow.min_cut_edges],
        "flow_paths": [
            {
                "nodes": list(p.nodes),
                "total_value_usd": round(p.total_value_usd, 2),
                "hops": p.hops,
            }
            for p in flow.flow_paths
        ],
    }


@router.post(
    "/cases/{case_id}/bridge-matches",
    summary="Match cross-chain bridge legs",
    description=(
        "Correlate a deposit/lock leg on one chain with the mint/unlock leg on another, so a "
        "trail that breaks at a bridge can be resumed on the destination chain."
    ),
)
async def run_bridge_matching(
    case_id: UUID,
    request: BridgeRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _require_case(session, case_id)
    transfers = await _load_transfers(session, case_id)

    matches = match_bridge_transfers(
        transfers,
        transfers,
        window_seconds=request.window_seconds,
        value_tolerance_pct=request.value_tolerance_pct,
        bridge_addresses=request.bridge_addresses,
    )

    return {
        "case_id": str(case_id),
        "transfer_count": len(transfers),
        "chains": sorted({t.chain for t in transfers}),
        "match_count": len(matches),
        "matches": [
            {
                "source_chain": m.source_chain,
                "source_tx": m.source_tx,
                "source_address": m.source_address,
                "destination_chain": m.destination_chain,
                "destination_tx": m.destination_tx,
                "destination_address": m.destination_address,
                "value_usd": round(m.value_usd, 2),
                "value_delta_pct": round(m.value_delta_pct, 4),
                "elapsed_seconds": m.elapsed_seconds,
                "confidence": round(m.confidence, 4),
                "bridge_address": m.bridge_address,
            }
            for m in matches
        ],
    }


@router.post(
    "/cases/{case_id}/p2p-correlation",
    summary="Correlate fiat payments with on-chain releases",
    description=(
        "Match victim UPI/IMPS payments reported through the 1930 / I4C portal against the "
        "on-chain escrow releases they paid for, using a timestamp and value window."
    ),
)
async def run_p2p_correlation(
    case_id: UUID,
    request: P2PRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _require_case(session, case_id)
    transfers = await _load_transfers(session, case_id)

    payments = [
        FiatPayment(
            reference_id=p.reference_id,
            payer_account=p.payer_account,
            payee_account=p.payee_account,
            amount_inr=p.amount_inr,
            timestamp=p.timestamp,
            rail=p.rail,
        )
        for p in request.payments
    ]

    correlations = correlate_fiat_to_chain(
        payments,
        transfers,
        window_seconds=request.window_seconds,
        usd_inr_rate=request.usd_inr_rate,
        amount_tolerance_pct=request.amount_tolerance_pct,
    )

    return {
        "case_id": str(case_id),
        "payment_count": len(payments),
        "release_count": len(transfers),
        "match_count": len(correlations),
        "matches": [
            {
                "payment_reference": c.payment_reference,
                "payer_account": c.payer_account,
                "payee_account": c.payee_account,
                "chain_tx": c.chain_tx,
                "crypto_address": c.crypto_address,
                "amount_inr": round(c.amount_inr, 2),
                "value_usd": round(c.value_usd, 2),
                "implied_rate": round(c.implied_rate, 4),
                "elapsed_seconds": c.elapsed_seconds,
                "confidence": round(c.confidence, 4),
            }
            for c in correlations
        ],
    }


async def _evidence_records(session: AsyncSession, case_id: UUID) -> list[EvidenceRecord]:
    """The case's transaction rows, frozen as hashable evidence records."""
    stmt = (
        select(Transaction, Wallet.chain, Wallet.address)
        .join(Wallet, Transaction.wallet_id == Wallet.id)
        .where(Wallet.case_id == case_id)
        .order_by(Transaction.timestamp.asc(), Transaction.tx_hash.asc())
    )
    rows = (await session.execute(stmt)).all()

    records: list[EvidenceRecord] = []
    seen: set[str] = set()
    for tx, chain, wallet_address in rows:
        if tx.tx_hash in seen:
            continue
        seen.add(tx.tx_hash)
        records.append(
            EvidenceRecord(
                record_id=tx.tx_hash,
                record_type="transaction",
                payload={
                    "tx_hash": tx.tx_hash,
                    "chain": chain,
                    "block_number": tx.block_number,
                    "timestamp": tx.timestamp.isoformat(),
                    "from_address": tx.from_address,
                    "to_address": tx.to_address,
                    "value": tx.value,
                    "value_usd": None if tx.value_usd is None else float(tx.value_usd),
                    "token_symbol": tx.token_symbol,
                    "is_suspicious": tx.is_suspicious,
                    "tracked_wallet": wallet_address,
                },
                source=f"trace-x:postgres:transactions:{chain}",
            )
        )
    return records


@router.post(
    "/cases/{case_id}/evidence-certificate",
    summary="Generate a Section 63 BSA evidence certificate",
    description=(
        "Produce the statutory electronic-evidence certificate required under Section 63 of the "
        "Bharatiya Sakshya Adhiniyam, 2023 (formerly Section 65B of the Indian Evidence Act): "
        "per-record SHA-256 hashes, a Merkle root and hash chain, extraction environment "
        "metadata, and the declaration for the Investigating Officer's signature."
    ),
)
async def create_evidence_certificate(
    case_id: UUID,
    request: EvidenceCertificateRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    case = await _require_case(session, case_id)
    records = await _evidence_records(session, case_id)

    certificate = build_certificate(
        records,
        case_number=case.case_number,
        investigating_officer=request.investigating_officer,
        system_metadata={
            "platform": "TRACE-X",
            "designation": request.designation,
            "place": request.place,
            "case_title": case.title,
        },
    )
    verified, mismatches = verify_certificate(certificate, records)

    return {
        "case_id": str(case_id),
        "case_number": case.case_number,
        "certificate_id": certificate.certificate_id,
        "generated_at": certificate.generated_at.isoformat(),
        "record_count": certificate.record_count,
        "merkle_root": certificate.merkle_root,
        "chain_tip": certificate.chain_tip,
        "record_hashes": list(certificate.record_hashes),
        "hash_chain": list(certificate.hash_chain),
        "system_metadata": certificate.system_metadata,
        "declaration": certificate.declaration,
        "self_verified": verified,
        "verification_errors": mismatches,
    }


@router.post(
    "/cases/{case_id}/evidence-certificate.pdf",
    summary="Download the Section 63 BSA evidence certificate as PDF",
    description="The same statutory certificate, rendered as a signed-ready PDF for court filing.",
    response_class=StreamingResponse,
)
async def download_evidence_certificate(
    case_id: UUID,
    request: EvidenceCertificateRequest,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    case = await _require_case(session, case_id)
    records = await _evidence_records(session, case_id)

    certificate = build_certificate(
        records,
        case_number=case.case_number,
        investigating_officer=request.investigating_officer,
        system_metadata={
            "platform": "TRACE-X",
            "designation": request.designation,
            "place": request.place,
            "case_title": case.title,
        },
    )
    pdf = generate_certificate_pdf(certificate)
    filename = f"{certificate.certificate_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/cases/{case_id}/summary",
    summary="Forensic summary for a case",
    description=(
        "One call for the forensics dashboard: transfer volume, entity clusters, laundering "
        "motifs and the headline taint figures for the case."
    ),
)
async def get_forensic_summary(
    case_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    await _require_case(session, case_id)
    transfers = await _load_transfers(session, case_id)

    clusters = build_clusters(transfers)
    motifs = detect_motifs(transfers)
    sources = await _default_sources(session, case_id, transfers)
    taint = propagate_haircut(transfers, sources) if sources else {}

    counts: dict[str, int] = {}
    for match in motifs:
        counts[match.motif] = counts.get(match.motif, 0) + 1

    addresses = {t.from_address for t in transfers} | {t.to_address for t in transfers}
    return {
        "case_id": str(case_id),
        "transfer_count": len(transfers),
        "address_count": len(addresses),
        "total_value_usd": round(sum(t.value_usd for t in transfers), 2),
        "chains": sorted({t.chain for t in transfers}),
        "cluster_count": len(clusters),
        "largest_cluster": max((c.member_count for c in clusters), default=0),
        "motif_counts": counts,
        "top_motifs": [
            {
                "motif": m.motif,
                "value_usd": round(m.value_usd, 2),
                "addresses": list(m.addresses[:6]),
                "confidence": round(m.confidence, 4),
            }
            for m in motifs[:5]
        ],
        "taint": {
            "sources": sources,
            "tainted_address_count": len(taint),
            "total_tainted_usd": round(sum(r.tainted_value_usd for r in taint.values()), 2),
            "top_destinations": taint_summary(taint, top_n=5),
        },
    }
