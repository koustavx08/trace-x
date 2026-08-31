from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .core import get_settings, setup_logging, init_db, close_db, register_exception_handlers, get_logger
from .api.v1 import api_router
from .graph.client import Neo4jClient
from .providers.factory import ProviderFactory
from .auth import audit_logger, limiter

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("application_starting", app_name=settings.APP_NAME, env=settings.APP_ENV)

    await init_db()
    logger.info("database_initialized")

    await Neo4jClient.initialize()
    logger.info("neo4j_initialized")

    ProviderFactory.initialize()
    logger.info("providers_initialized")

    # Initialize audit logger
    await audit_logger.log(
        action="system_startup",
        success=True,
        metadata={"app_name": settings.APP_NAME, "env": settings.APP_ENV},
    )

    yield

    # Log shutdown
    await audit_logger.log(
        action="system_shutdown",
        success=True,
    )
    await audit_logger.close()

    await ProviderFactory.close_all()
    logger.info("providers_closed")

    await Neo4jClient.close()
    logger.info("neo4j_closed")

    await close_db()
    logger.info("application_shutdown")


app = FastAPI(
    title=settings.APP_NAME,
    description="TRACE-X - Real-Time Cryptocurrency Fraud Attribution & Investigation Platform",
    version="0.1.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    openapi_url="/openapi.json" if settings.is_development else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# --- WS1 auth hardening: rate-limit middleware registration ---
# Per-route limits (e.g. strict throttling on /auth/login, /auth/refresh)
# are declared where those routes live (api/v1/auth.py) via
# @limiter.limit(...), using the shared `limiter` instance from src.auth.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
# --- end rate-limit middleware registration ---

register_exception_handlers(app)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "description": "TRACE-X - Real-Time Cryptocurrency Fraud Attribution & Investigation Platform",
        "docs": "/docs" if settings.is_development else "disabled",
    }