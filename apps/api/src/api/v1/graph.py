from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core import NotFoundError, get_session
from src.graph.client import Neo4jClient
from src.graph.models import ConfidenceLevel, EntityType
from src.graph.queries import graph_queries
from src.graph.repository import graph_repository
from src.intelligence import entity_intelligence
from src.models import Wallet

router = APIRouter(prefix="/graph", tags=["graph"])


class WalletGraphRequest(BaseModel):
    wallet_id: UUID
    depth: int = Field(2, ge=1, le=10)
    limit: int = Field(100, ge=10, le=500)


class PathToVASPRequest(BaseModel):
    wallet_id: UUID
    max_hops: int = Field(6, ge=1, le=10)
    min_confidence: ConfidenceLevel = ConfidenceLevel.PROBABLE


class EntityLookupRequest(BaseModel):
    address: str
    chain: str


class SubgraphRequest(BaseModel):
    addresses: list[str]
    chain: str
    depth: int = Field(2, ge=1, le=10)


class ClusterDetectionRequest(BaseModel):
    chain: str
    min_cluster_size: int = Field(3, ge=2, le=10)


class PatternDetectionRequest(BaseModel):
    chain: str
    pattern_type: str = Field(..., pattern="^(peel_chain|round_amount|rapid_movement|mixer)$")
    time_window_hours: int = Field(24, ge=1, le=168)


@router.post(
    "/wallets/sync",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Sync wallet to graph",
    description="Sync a wallet to the graph database as a background task.",
)
async def sync_wallet_to_graph(
    wallet_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    from src.workers.tasks import graph_sync_task

    task = graph_sync_task.delay(str(wallet_id))
    return {"status": "queued", "wallet_id": str(wallet_id), "task_id": task.id}


@router.post(
    "/subgraph",
    summary="Get subgraph",
    description="Retrieve a subgraph for the given addresses and chain.",
)
async def get_subgraph(request: SubgraphRequest):
    subgraph = await graph_repository.get_subgraph(request.addresses, request.chain, request.depth)
    return subgraph


@router.post(
    "/wallets/{wallet_id}/paths-to-vasp",
    summary="Find paths to VASP",
    description="Find transaction paths from a wallet to VASPs (exchanges/bridges) within a maximum number of hops.",
)
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


@router.post(
    "/wallets/{wallet_id}/mixer-check",
    summary="Check mixer interaction",
    description="Check for mixer interactions associated with a wallet address.",
)
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


@router.post(
    "/patterns/detect",
    summary="Detect patterns",
    description="Detect specified patterns (peel chain, round amount, rapid movement, mixer) in blockchain graph data.",
)
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


@router.post(
    "/clusters/detect",
    summary="Detect clusters",
    description="Detect clusters of related wallet addresses on a blockchain.",
)
async def detect_clusters(request: ClusterDetectionRequest):
    clusters = await graph_repository.detect_clusters(request.chain, request.min_cluster_size)
    return {"chain": request.chain, "clusters": clusters, "count": len(clusters)}


@router.get(
    "/wallets/{wallet_id}/stats",
    summary="Get wallet stats",
    description="Retrieve statistics for a wallet address in the graph.",
)
async def get_wallet_stats(
    wallet_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    stats = await graph_repository.get_wallet_stats(wallet.address, wallet.chain)
    return stats


@router.get(
    "/wallets/{wallet_id}/centrality",
    summary="Get wallet centrality",
    description="Retrieve centrality metrics for a wallet using the specified algorithm (pagerank, betweenness, degree).",
)
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


@router.get(
    "/wallets/{wallet_id}/temporal-flow",
    summary="Get temporal flow",
    description="Retrieve temporal flow data for a wallet address within a date range.",
)
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


@router.post(
    "/entities/lookup",
    summary="Lookup entity",
    description="Lookup entity intelligence for a wallet address on a specific chain.",
)
async def lookup_entity(request: EntityLookupRequest):
    entity = await entity_intelligence.lookup_entity(request.address, request.chain)
    if not entity:
        return {"found": False}
    return {"found": True, "entity": entity.to_dict()}


@router.post(
    "/entities/enrich",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enrich wallet",
    description="Enrich wallet entity data as a background task.",
)
async def enrich_wallet(
    wallet_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    wallet = await session.get(Wallet, wallet_id)
    if not wallet:
        raise NotFoundError("Wallet", str(wallet_id))

    from src.workers.tasks import entity_enrichment_task

    task = entity_enrichment_task.delay(str(wallet_id))
    return {"status": "queued", "wallet_id": str(wallet_id), "task_id": task.id}


@router.post(
    "/entities/sync",
    summary="Sync entities",
    description="Sync entity intelligence data to the graph.",
)
async def sync_entities():
    stats = await entity_intelligence.sync_to_graph()
    return stats


@router.get(
    "/health",
    summary="Graph health",
    description="Check the health status of the Neo4j graph database connection.",
)
async def graph_health():
    try:
        await Neo4jClient.initialize()
        async with Neo4jClient.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.consume()
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "neo4j": "disconnected", "error": str(e)}
