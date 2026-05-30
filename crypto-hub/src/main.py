from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting crypto-hub...")
    yield
    # Shutdown
    print("Shutting down crypto-hub...")

app = FastAPI(
    title="Crypto Hub",
    description="币安Alpha代币交易模块",
    version="0.1.0",
    lifespan=lifespan
)

@app.get("/health")
async def health():
    return {"status": "ok", "module": "crypto"}