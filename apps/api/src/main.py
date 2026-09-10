from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .api.v1 import api_router
from .auth import audit_logger, limiter
from .core import (
    close_db,
    get_logger,
    get_settings,
    init_db,
    register_exception_handlers,
    setup_logging,
)
from .graph.client import Neo4jClient
from .providers.factory import ProviderFactory

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
    contact={
        "name": "TRACE-X Support",
        "email": "support@trace-x.example",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    terms_of_service="https://trace-x.example/terms",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


# --- WS1 auth hardening: rate-limit middleware registration ---
# Per-route limits (e.g. strict throttling on /auth/login, /auth/refresh)
# are declared where those routes live (api/v1/auth.py) via
# @limiter.limit(...), using the shared `limiter` instance from src.auth.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)
# --- end rate-limit middleware registration ---

register_exception_handlers(app)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# Exposes http_requests_total / http_request_duration_seconds_bucket at
# /api/v1/metrics, which is exactly what docker/prometheus/prometheus.yml
# and rules/alerts.yml (HighErrorRate, HighLatency) already expect.
Instrumentator().instrument(app).expose(app, endpoint=f"{settings.API_V1_PREFIX}/metrics")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "0.1.0",
        "description": "TRACE-X - Real-Time Cryptocurrency Fraud Attribution & Investigation Platform",
        "docs": "/docs" if settings.is_development else "disabled",
    }
