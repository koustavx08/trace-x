from fastapi import APIRouter

from src.ai import ai_router

from .analysis import router as analysis_router
from .auth import router as auth_router
from .cases import router as cases_router
from .graph import router as graph_router
from .health import router as health_router
from .investigations import router as investigations_router
from .reports import router as reports_router
from .risk import router as risk_router
from .wallets import router as wallets_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router)
api_router.include_router(cases_router)
api_router.include_router(wallets_router)
api_router.include_router(investigations_router)
api_router.include_router(reports_router)
api_router.include_router(analysis_router)
api_router.include_router(graph_router)
api_router.include_router(risk_router)
api_router.include_router(ai_router)
