from fastapi import APIRouter, Depends

from src.api.dependencies import get_current_user, get_current_user_id
from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1", dependencies=[Depends(get_current_user)])


@router.get("/portfolio-targets/active")
def get_active_targets(
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    store=Depends(get_runtime_store),  # noqa: B008
) -> list[dict]:
    return store.list_active_target_positions(user_id=user_id)
