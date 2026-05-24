from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from datetime import datetime

from src.storage.dependencies import get_runtime_store

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    """返回仪表盘页面"""
    with open("src/api/dashboard.html", "r", encoding="utf-8") as f:
        return f.read()


@router.get("/api/v1/dashboard/status")
def get_system_status(store=Depends(get_runtime_store)):
    """获取系统状态"""
    reconciliation = store.get_reconciliation_status()
    return {
        "timestamp": datetime.now().isoformat(),
        "mode": "shadow",
        "open_orders": reconciliation["open_orders"],
        "healthy": reconciliation["healthy"],
        "active_targets": len(store.list_active_target_positions()),
        "recent_decisions": len(store.list_decision_runs()),
    }


@router.get("/api/v1/dashboard/decisions")
def get_recent_decisions(store=Depends(get_runtime_store)):
    """获取最近的决策"""
    return {"decisions": store.list_decision_runs()[:10]}


@router.get("/api/v1/dashboard/orders")
def get_recent_orders(store=Depends(get_runtime_store)):
    """获取最近的订单"""
    return {"orders": store.list_ready_execution_plans()[:10]}


@router.get("/api/v1/dashboard/portfolio")
def get_portfolio_summary(store=Depends(get_runtime_store)):
    """获取组合摘要"""
    targets = store.list_active_target_positions()
    return {
        "active_targets": len(targets),
        "targets": targets[:10],
    }
