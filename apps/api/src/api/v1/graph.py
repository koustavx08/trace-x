from uuid import UUID
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from ....core import get_session, NotFoundError
from ....models import Wallet, Case
from ....graph.client import Neo4jClient
from ....graph.repository import graph_repository
from ....graph.queries import graph_queries
from ....graph.models import GraphWallet, GraphTransaction, GraphEntity, EntityType, ConfidenceLevel
from ....intelligence import entity_intelligence
from ....services import wallet_analysis_service

router = APIRouter(prefix="/graph", tags=["graph"])


class WalletGraphRequest(BaseModel):
    wallet_id: UUID
    depth: int = Field(2, ge=1, le=4)
    limit: int = Field(100, ge=10, le=500)


class PathToVASPRequest(BaseModel):
    wallet_id: UUID
    max_hops: int = Field(6, ge=1, le=10)
    min_confidence: ConfidenceLevel = ConfidenceLevel.PROBABLE


class EntityLookupRequest(BaseModel):
    address: str
    chain: str


class SubgraphRequest(BaseModel):
    addresses: List[str]
    chain: str
    depth: int = Field(2, ge=1, le=3)


class ClusterDetectionRequest(BaseModel):
    chain: str
    min_cluster_size: int = Field(3, ge=2, le=10)


class PatternDetectionRequest(BaseModel):
    chain: str
    pattern_type: str = Field(..., pattern="^(peel_chain|round_amount|rapid_movement|mixer)$")
    time_window_hours: int = Field(24, ge=1, le=168)


@router.post("/wallets/sync", status_code=status.HTTP_202_ACCEPTED)
async def sync_wallet_to_graph(
    wallet_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    graph_wallet = GraphWallet(
        address=wallet.address,
        chain=wallet.chain,
        label=wallet.label,
        risk_score=float(wallet.risk_score),
        first_seen=wallet.created_at,
        last_seen=wallet.updated_at,
        entity_name=wallet.entity_name,
        entity_type=wallet.entity_type,
        entity_confidence=ConfidenceLevel(wallet.entity_confidence) if wallet.entity_confidence else ConfidenceLevel.UNKNOWN,
    )
    await graph_repository.upsert_wallet(graph_wallet)

    from ....models import Transaction
    from sqlalchemy import select
    result = await session.execute(select(Transaction).where(Transaction.wallet_id == wallet_id))
    transactions = result.scalars().all()

    for tx in transactions:
        graph_tx = GraphTransaction(
            tx_hash=tx.tx_hash,
            chain=wallet.chain,
            block_number=tx.block_number,
            timestamp=tx.timestamp,
            from_address=tx.from_address,
            to_address=tx.to_address,
            value=tx.value,
            value_usd=tx.value_usd,
            token_address=tx.token_address,
            token_symbol=tx.token_symbol,
            method=tx.method,
            is_suspicious=tx.is_suspicious,
            metadata=tx.metadata,
        )
        await graph_repository.upsert_transaction(graph_tx)
        await graph_repository.link_wallet_transaction(wallet.address, wallet.chain, tx.tx_hash, "sent")
        await graph_repository.link_wallet_transaction(tx.to_address, wallet.chain, tx.tx_hash, "received")

    if wallet.entity_name and wallet.entity_confidence:
        entity = GraphEntity(
            name=wallet.entity_name,
            entity_type=wallet.entity_type,
            address=wallet.address,
            chain=wallet.chain,
            confidence=ConfidenceLevel(wallet.entity_confidence),
            source="analysis",
        )
        await graph_repository.upsert_entity(entity)
        await graph_repository.link_wallet_entity(wallet.address, wallet.chain, wallet.address)

    await entity_intelligence.enrich_wallet(wallet.address, wallet.chain)

    return {"status": "synced", "wallet_id": str(wallet_id), "transactions": len(transactions)}


@router.post("/subgraph")
async def get_subgraph(request: SubgraphRequest):
    subgraph = await graph_repository.get_subgraph(request.addresses, request.chain, request.depth)
    return subgraph


@router.post("/wallets/{wallet_id}/paths-to-vasp")
async def find_paths_to_vasp(
    wallet_id: UUID,
    request: PathToVASPRequest,
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    paths = await graph_repository.find_paths_to_entities(
        start_address=wallet.address,
        chain=wallet.chain,
        entity_types=[EntityType.EXCHANGE, EntityType.BRIDGE],
        max_depth=request.max_hops,
        min_confidence=request.min_confidence,
        limit=10,
    )
    return {"wallet_id": str(wallet_id), "paths": [p.to_dict() for p in paths]}


@router.post("/wallets/{wallet_id}/mixer-check")
async def check_mixer_interaction(
    wallet_id: UUID,
    max_hops: int = Query(4, ge=1, le=6),
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    results = await graph_queries.find_mixer_interactions(
        address=wallet.address,
        chain=wallet.chain,
        max_hops=max_hops,
    )
    return {"wallet_id": str(wallet_id), "mixer_interactions": results}


@router.post("/patterns/detect")
async def detect_patterns(request: PatternDetectionRequest):
    if request.pattern_type == "peel_chain":
        results = await graph_queries.detect_peel_chains(
            chain=request.chain,
            min_hops=3,
            time_window_hours=request.time_window_hours,
        )
    elif request.pattern_type == "round_amount":
        results = await graph_queries.detect_round_amount_patterns(
            chain=request.chain,
            min_occurrences=3,
            time_window_hours=request.time_window_hours,
        )
    elif request.pattern_type == "rapid_movement":
        results = await graph_queries.detect_rapid_movement(
            chain=request.chain,
            max_time_between_txs_seconds=300,
            min_hops=3,
        )
    elif request.pattern_type == "mixer":
        results = await graph_queries.find_mixer_interactions(
            address="",
            chain=request.chain,
            max_hops=4,
        )
    else:
        results = []

    return {"pattern_type": request.pattern_type, "results": results, "count": len(results)}


@router.post("/clusters/detect")
async def detect_clusters(request: ClusterDetectionRequest):
    clusters = await graph_repository.detect_clusters(request.chain, request.min_cluster_size)
    return {"chain": request.chain, "clusters": clusters, "count": len(clusters)}


@router.get("/wallets/{wallet_id}/stats")
async def get_wallet_stats(
    wallet_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    stats = await graph_repository.get_wallet_stats(wallet.address, wallet.chain)
    return stats


@router.get("/wallets/{wallet_id}/centrality")
async def get_wallet_centrality(
    wallet_id: UUID,
    algorithm: str = Query("pagerank", pattern="^(pagerank|betweenness|degree)$"),
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    centrality = await graph_queries.get_wallet_centrality(
        chain=wallet.chain,
        algorithm=algorithm,
        top_n=100,
    )
    return {"wallet_id": str(wallet_id), "algorithm": algorithm, "centrality": centrality}


@router.get("/wallets/{wallet_id}/temporal-flow")
async def get_temporal_flow(
    wallet_id: UUID,
    start_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    bucket: str = Query("day", pattern="^(hour|day|week)$"),
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    from datetime import datetime
    flow = await graph_queries.get_temporal_flow(
        address=wallet.address,
        chain=wallet.chain,
        start_date=datetime.fromisoformat(start_date),
        end_date=datetime.fromisoformat(end_date),
        bucket=bucket,
    )
    return {"wallet_id": str(wallet_id), "temporal_flow": flow}


@router.post("/entities/lookup")
async def lookup_entity(request: EntityLookupRequest):
    entity = await entity_intelligence.lookup_entity(request.address, request.chain)
    if not entity:
        return {"found": False}
    return {"found": True, "entity": entity.to_dict()}


@router.post("/entities/enrich")
async def enrich_wallet(
    wallet_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    entity = await entity_intelligence.enrich_wallet(wallet.address, wallet.chain)
    if not entity:
        return {"enriched": False}
    return {"enriched": True, "entity": entity.to_dict()}


@router.post("/entities/sync")
async def sync_entities():
    stats = await entity_intelligence.sync_to_graph()
    return stats


@router.get("/health")
async def graph_health():
    try:
        await Neo4jClient.initialize()
        async with Neo4jClient.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.consume()
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "neo4j": "disconnected", "error": str(e)}