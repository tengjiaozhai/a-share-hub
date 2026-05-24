from fastapi import APIRouter, Depends

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
def get_ready_plans(store=Depends(get_runtime_store)) -> list[dict]:
    return [serialize_execution_plan(plan) for plan in store.list_ready_execution_plans()]


@router.post("/execution-plans/{plan_id}/ack")
def acknowledge_plan(plan_id: str, store=Depends(get_runtime_store)) -> dict:
    store.mark_plan_acknowledged(plan_id)
    return {"plan_id": plan_id, "acknowledged": True}
