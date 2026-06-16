from fastapi import APIRouter, Depends, Query

from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1")


@router.get("/reconciliation/status")
def get_reconciliation_status(
    run_context_id: str | None = Query(default=None),
    store=Depends(get_runtime_store),
) -> dict:
    return store.get_reconciliation_status(run_context_id=run_context_id)
