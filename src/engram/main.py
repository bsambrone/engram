from fastapi import FastAPI

app = FastAPI(title="Engram", version="0.1.0", description="Digital engram platform")


@app.get("/health")
async def health():
    return {"status": "ok"}
