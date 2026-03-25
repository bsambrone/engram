"""Router aggregation."""

from fastapi import APIRouter

from engram.api.routes.config_routes import router as config_router
from engram.api.routes.engram import router as engram_router
from engram.api.routes.identity import router as identity_router
from engram.api.routes.ingest import router as ingest_router
from engram.api.routes.memories import router as memories_router
from engram.api.routes.people import router as people_router
from engram.api.routes.photos import router as photos_router
from engram.api.routes.sources import router as sources_router
from engram.api.routes.tokens import router as tokens_router

api_router = APIRouter(prefix="/api")
api_router.include_router(tokens_router)
api_router.include_router(config_router)
api_router.include_router(engram_router)
api_router.include_router(identity_router)
api_router.include_router(ingest_router)
api_router.include_router(memories_router)
api_router.include_router(people_router)
api_router.include_router(photos_router)
api_router.include_router(sources_router)
