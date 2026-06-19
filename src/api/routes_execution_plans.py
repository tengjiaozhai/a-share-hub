from fastapi import APIRouter, Depends

from src.api.dependencies import get_current_user_id
from src.storage.dependencies import get_runtime_store

router = APIRouter(prefix="/api/v1")


def serialize_execution_plan(plan: dict) -> dict:
    return {
        "plan_id": plan["plan_id"],
        "symbol": plan["symbol"],
        "target_value": plan["target_value"],
        "action": plan["action"],
        "reason": plan["reason"],
    }


@router.get("/execution-plans/ready")
def get_ready_plans(
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    store=Depends(get_runtime_store),  # noqa: B008
) -> list[dict]:
    return [serialize_execution_plan(plan) for plan in store.list_ready_execution_plans(user_id=user_id)]


@router.post("/execution-plans/{plan_id}/ack")
def acknowledge_plan(
    plan_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    store=Depends(get_runtime_store),  # noqa: B008
) -> dict:
    store.mark_plan_acknowledged(user_id=user_id, plan_id=plan_id)
    return {"plan_id": plan_id, "acknowledged": True}
