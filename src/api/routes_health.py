from fastapi import APIRouter, HTTPException

from src.storage.health import probe_runtime_database_from_settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def health_ready() -> dict:
    result = probe_runtime_database_from_settings()
    if not result["ok"]:
        raise HTTPException(status_code=503, detail=result)
    return {"status": "ok", **result}
