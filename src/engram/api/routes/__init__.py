"""Router aggregation."""

from fastapi import APIRouter

from engram.api.routes.config_routes import router as config_router
from engram.api.routes.ingest import router as ingest_router
from engram.api.routes.tokens import router as tokens_router

api_router = APIRouter(prefix="/api")
api_router.include_router(tokens_router)
api_router.include_router(config_router)
api_router.include_router(ingest_router)
