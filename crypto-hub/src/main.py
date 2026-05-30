from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes_dashboard import router as dashboard_router


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

# 注册路由
app.include_router(dashboard_router)


@app.get("/health")
async def health():
    return {"status": "ok", "module": "crypto"}
