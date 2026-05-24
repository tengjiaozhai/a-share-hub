from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from datetime import datetime
import json

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    """返回仪表盘页面"""
    with open("src/api/dashboard.html", "r", encoding="utf-8") as f:
        return f.read()

@router.get("/api/v1/dashboard/status")
def get_system_status():
    """获取系统状态"""
    return {
        "timestamp": datetime.now().isoformat(),
        "system": {
            "name": "A股自动交易系统",
            "version": "0.1.0",
            "mode": "shadow",
            "live_trading": False,
        },
        "components": {
            "database": {"status": "connected", "type": "PostgreSQL"},
            "llm": {"status": "connected", "provider": "DeepSeek"},
            "data_source": {"status": "connected", "provider": "AkShare"},
        },
        "stats": {
            "total_decisions": 0,
            "total_orders": 0,
            "success_rate": 0,
            "last_update": datetime.now().isoformat(),
        }
    }

@router.get("/api/v1/dashboard/decisions")
def get_recent_decisions():
    """获取最近的决策"""
    return {
        "decisions": [
            {
                "id": "D001",
                "timestamp": datetime.now().isoformat(),
                "symbol": "600519.SH",
                "action": "BUY",
                "confidence": 75,
                "status": "executed",
            }
        ]
    }

@router.get("/api/v1/dashboard/orders")
def get_recent_orders():
    """获取最近的订单"""
    return {
        "orders": [
            {
                "id": "O001",
                "timestamp": datetime.now().isoformat(),
                "symbol": "600519.SH",
                "side": "BUY",
                "quantity": 100,
                "status": "FILLED",
                "pnl": 0,
            }
        ]
    }

@router.get("/api/v1/dashboard/portfolio")
def get_portfolio_summary():
    """获取组合摘要"""
    return {
        "total_value": 1000000,
        "cash": 900000,
        "positions_value": 100000,
        "positions": [
            {
                "symbol": "600519.SH",
                "quantity": 100,
                "avg_price": 1420.0,
                "current_price": 1425.0,
                "pnl": 500,
                "pnl_pct": 0.35,
            }
        ],
        "daily_pnl": 500,
        "total_pnl": 500,
    }
