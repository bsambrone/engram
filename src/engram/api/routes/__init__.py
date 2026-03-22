"""Router aggregation."""

from fastapi import APIRouter

from engram.api.routes.tokens import router as tokens_router

api_router = APIRouter(prefix="/api")
api_router.include_router(tokens_router)
