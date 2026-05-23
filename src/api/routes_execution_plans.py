from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(prefix="/api/v1")

def serialize_execution_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """序列化执行计划"""
    return {
        "plan_id": plan.get("plan_id", ""),
        "symbol": plan.get("symbol", ""),
        "target_value": plan.get("target_value", 0),
        "action": plan.get("action", ""),
    }

@router.get("/execution-plans/ready")
def get_ready_plans() -> list[dict]:
    """获取待执行的计划"""
    return []

@router.post("/execution-plans/{plan_id}/ack")
def acknowledge_plan(plan_id: str) -> dict:
    """确认执行计划"""
    return {"plan_id": plan_id, "acknowledged": True}
