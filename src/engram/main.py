from fastapi import FastAPI

from engram.api.routes import api_router

app = FastAPI(title="Engram", version="0.1.0", description="Digital engram platform")
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
