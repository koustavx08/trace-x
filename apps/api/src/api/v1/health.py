from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis
from neo4j import AsyncGraphDatabase
import structlog

from ....core import get_settings, get_session
from ....schemas import HealthResponse

logger = structlog.get_logger(__name__)
router = APIRouter()

settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check(session: AsyncSession = Depends(get_session)) -> HealthResponse:
    services = {
        "database": "disconnected",
        "neo4j": "disconnected",
        "redis": "disconnected",
    }
    overall_status = "healthy"

    try:
        await session.execute(text("SELECT 1"))
        services["database"] = "connected"
    except Exception as e:
        logger.warning("health_check_database_failed", error=str(e))
        services["database"] = "disconnected"
        overall_status = "degraded"

    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        await redis_client.ping()
        await redis_client.close()
        services["redis"] = "connected"
    except Exception as e:
        logger.warning("health_check_redis_failed", error=str(e))
        services["redis"] = "disconnected"
        overall_status = "degraded"

    try:
        driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        await driver.verify_connectivity()
        await driver.close()
        services["neo4j"] = "connected"
    except Exception as e:
        logger.warning("health_check_neo4j_failed", error=str(e))
        services["neo4j"] = "disconnected"
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version="0.1.0",
        timestamp="2024-01-01T00:00:00Z",
        services=services,
    )


@router.get("/health/ready")
async def readiness_check() -> dict:
    return {"status": "ready"}


@router.get("/health/live")
async def liveness_check() -> dict:
    return {"status": "alive"}