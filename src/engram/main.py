from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from engram.api.routes import api_router

app = FastAPI(title="Engram", version="0.1.0", description="Digital engram platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
