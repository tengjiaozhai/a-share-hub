from fastapi import APIRouter
from typing import Dict, Any

router = APIRouter(prefix="/api/v1")

@router.post("/broker-events")
def receive_broker_event(event: Dict[str, Any]) -> dict:
    """接收经纪商事件"""
    return {"received": True, "event_type": event.get("event_type", "")}

@router.get("/reconciliation/status")
def get_reconciliation_status() -> dict:
    """获取对账状态"""
    return {"reconciled": True, "last_check": "2026-05-23T15:00:00"}
