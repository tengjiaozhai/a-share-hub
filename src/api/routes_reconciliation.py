from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_current_user, get_user_runtime_store
from src.storage.runtime_store import RuntimeStore

router = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_user)])


@router.get("/reconciliation/status")
def get_reconciliation_status(
    run_context_id: str | None = Query(default=None),
    store: RuntimeStore = Depends(get_user_runtime_store),
) -> dict:
    return store.get_reconciliation_status(run_context_id=run_context_id)