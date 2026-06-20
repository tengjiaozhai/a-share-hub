from fastapi import APIRouter, Depends

from src.api.dependencies import get_current_user, get_user_runtime_store
from src.storage.runtime_store import RuntimeStore

router = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_user)])


@router.get("/portfolio-targets/active")
def get_active_targets(
    store: RuntimeStore = Depends(get_user_runtime_store),
) -> list[dict]:
    return store.list_active_target_positions()