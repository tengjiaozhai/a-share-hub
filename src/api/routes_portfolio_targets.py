from fastapi import APIRouter, Depends

from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1")


@router.get("/portfolio-targets/active")
def get_active_targets(store=Depends(get_runtime_store)) -> list[dict]:
    return store.list_active_target_positions()
