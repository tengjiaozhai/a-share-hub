from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_current_user, get_current_user_id
from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_user)])


@router.get("/reconciliation/status")
def get_reconciliation_status(
    run_context_id: str | None = Query(default=None),
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    store=Depends(get_runtime_store),  # noqa: B008
) -> dict:
    return store.get_reconciliation_status(user_id=user_id, run_context_id=run_context_id)
