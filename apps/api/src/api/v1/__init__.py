from fastapi import APIRouter

from .health import router as health_router
from .cases import router as cases_router
from .wallets import router as wallets_router
from .investigations import router as investigations_router
from .reports import router as reports_router
from .analysis import router as analysis_router
from .graph import router as graph_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(cases_router)
api_router.include_router(wallets_router)
api_router.include_router(investigations_router)
api_router.include_router(reports_router)
api_router.include_router(analysis_router)
api_router.include_router(graph_router)