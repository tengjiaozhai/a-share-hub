from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime
import uuid

from src.storage.dependencies import get_runtime_store

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    """返回交易工作台页面"""
    with open("src/api/dashboard.html", "r", encoding="utf-8") as f:
        return f.read()


@router.get("/api/v1/dashboard/workbench")
def get_workbench(store=Depends(get_runtime_store)):
    """获取工作台完整数据"""
    # 获取基础数据
    reconciliation = store.get_reconciliation_status()
    active_targets = store.list_active_target_positions()
    decision_runs = store.list_decision_runs()
    ready_plans = store.list_ready_execution_plans()
    kill_switch_active = store.get_kill_switch()

    # 构建最新运行时间线
    latest_run = _build_latest_run(store)

    # 构建历史数据
    history = {
        "decisions": decision_runs[:20],
        "orders": ready_plans[:20],
        "targets": active_targets[:20],
        "events": _get_recent_events(store)
    }

    # 构建风险数据
    risk = {
        "concentration_ratio": 0.2,
        "active_target_count": len(active_targets),
        "open_orders": reconciliation.get("open_orders", 0),
        "alerts": _get_alerts(store, reconciliation)
    }

    return {
        "mode": "shadow",
        "trade_date": datetime.now().strftime("%Y-%m-%d"),
        "last_run_at": latest_run.get("finished_at") or latest_run.get("started_at"),
        "services": {
            "database": "ok",
            "llm": "unknown",
            "market": "unknown"
        },
        "kill_switch": {
            "active": kill_switch_active
        },
        "config": _get_default_config(),
        "risk": risk,
        "latest_run": latest_run,
        "history": history
    }


@router.post("/api/v1/dashboard/run")
def run_decision(config: dict, store=Depends(get_runtime_store)):
    """同步运行一轮决策"""
    # 检查 kill switch
    if store.get_kill_switch():
        return _build_blocked_response("Kill Switch 已激活")

    # 生成 run_context_id
    run_context_id = f"wrk-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    started_at = datetime.now().isoformat()

    steps = []
    watchlist = config.get("watchlist", ["600519.SH"])
    execution_mode = config.get("execution_mode", "full")

    try:
        # 阶段1: 决策
        decision_items = []
        for symbol in watchlist:
            decision_run_id = store.insert_decision_run(
                symbol=symbol,
                prompt_hash=f"mock-{run_context_id}",
                model_name="mock-llm",
                raw_output=f'{{"symbol":"{symbol}","action":"BUY","confidence":80,"reason":"mock output"}}',
                parsed_action="BUY",
                confidence=80,
                target_position_ratio=0.1,
                reason="mock output",
                input_snapshot={
                    "market_context": {"run_context_id": run_context_id},
                    "symbol": symbol
                }
            )
            decision_items.append({
                "symbol": symbol,
                "action": "BUY",
                "confidence": 80,
                "reason": "mock output"
            })

        steps.append({
            "stage": "decision",
            "status": "done",
            "timestamp": datetime.now().isoformat(),
            "items": decision_items
        })

        # 阶段2: 目标仓位
        target_items = []
        for symbol in watchlist:
            capital_base = config.get("capital_base", 1000000)
            max_position_ratio = config.get("max_position_ratio", 0.2)
            target_value = int(capital_base * max_position_ratio / len(watchlist))

            target_position_id = store.insert_target_position(
                decision_run_id=decision_run_id,
                symbol=symbol,
                action="BUY",
                target_value=target_value,
                target_position_ratio=max_position_ratio / len(watchlist),
                expires_at=datetime.now().isoformat()
            )
            target_items.append({
                "symbol": symbol,
                "target_value": target_value,
                "target_position_ratio": max_position_ratio / len(watchlist)
            })

        steps.append({
            "stage": "target",
            "status": "done",
            "timestamp": datetime.now().isoformat(),
            "items": target_items
        })

        # 阶段3: 执行（如果 execution_mode=full）
        if execution_mode == "full":
            execute_items = []
            for symbol in watchlist:
                execution_order_id = store.insert_execution_order(
                    target_position_id=target_position_id,
                    symbol=symbol,
                    action="BUY",
                    quantity=100,
                    limit_price=100.0
                )
                store.insert_broker_order_event(
                    execution_order_id=execution_order_id,
                    event_id=f"evt-{uuid.uuid4().hex[:8]}",
                    event_type="FILLED",
                    payload={"broker_order_id": f"mock-{uuid.uuid4().hex[:8]}"}
                )
                execute_items.append({
                    "symbol": symbol,
                    "action": "BUY",
                    "quantity": 100,
                    "limit_price": 100.0,
                    "status": "FILLED"
                })

            steps.append({
                "stage": "execute",
                "status": "done",
                "timestamp": datetime.now().isoformat(),
                "items": execute_items
            })

            # 阶段4: 对账
            reconciliation = store.get_reconciliation_status()
            steps.append({
                "stage": "reconcile",
                "status": "done",
                "timestamp": datetime.now().isoformat(),
                "message": f"open_orders={reconciliation['open_orders']}, broker_event_count={reconciliation['broker_event_count']}, healthy={reconciliation['healthy']}"
            })

    except Exception as e:
        steps.append({
            "stage": "error",
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "message": str(e)
        })

    # 构建返回结果
    latest_run = {
        "run_context_id": run_context_id,
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(),
        "status": "completed",
        "steps": steps
    }

    # 获取完整工作台数据
    return get_workbench(store)


def _build_latest_run(store):
    """从数据库重建最新运行时间线"""
    decision_runs = store.list_decision_runs()
    if not decision_runs:
        return {
            "status": "idle",
            "steps": []
        }

    # 获取最新决策
    latest_decisions = decision_runs[:5]
    
    steps = []
    
    # 决策步骤
    decision_items = []
    for d in latest_decisions:
        decision_items.append({
            "symbol": d.get("symbol"),
            "action": d.get("parsed_action"),
            "confidence": d.get("confidence"),
            "reason": d.get("reason", "")
        })
    
    if decision_items:
        steps.append({
            "stage": "decision",
            "status": "done",
            "timestamp": latest_decisions[0].get("created_at"),
            "items": decision_items
        })

    # 目标仓位步骤
    active_targets = store.list_active_target_positions()
    if active_targets:
        target_items = []
        for t in active_targets[:5]:
            target_items.append({
                "symbol": t.get("symbol"),
                "target_value": t.get("target_value"),
                "target_position_ratio": t.get("target_position_ratio")
            })
        steps.append({
            "stage": "target",
            "status": "done",
            "timestamp": active_targets[0].get("created_at"),
            "items": target_items
        })

    # 执行步骤
    ready_plans = store.list_ready_execution_plans()
    if ready_plans:
        execute_items = []
        for p in ready_plans[:5]:
            execute_items.append({
                "symbol": p.get("symbol"),
                "action": p.get("action"),
                "quantity": 100,
                "limit_price": 100.0,
                "status": "FILLED"
            })
        steps.append({
            "stage": "execute",
            "status": "done",
            "timestamp": ready_plans[0].get("created_at"),
            "items": execute_items
        })

    # 对账步骤
    reconciliation = store.get_reconciliation_status()
    steps.append({
        "stage": "reconcile",
        "status": "done",
        "timestamp": datetime.now().isoformat(),
        "message": f"open_orders={reconciliation['open_orders']}, broker_event_count={reconciliation['broker_event_count']}, healthy={reconciliation['healthy']}"
    })

    return {
        "run_context_id": f"recovered-{datetime.now().strftime('%Y%m%d')}",
        "started_at": latest_decisions[0].get("created_at") if latest_decisions else None,
        "finished_at": datetime.now().isoformat(),
        "status": "completed",
        "steps": steps
    }


def _get_recent_events(store):
    """获取最近事件"""
    # 从 kill switch events 获取
    events = []
    # TODO: 从 store 获取 kill_switch_events
    return events


def _get_alerts(store, reconciliation):
    """获取告警信息"""
    alerts = []
    
    if reconciliation.get("healthy"):
        alerts.append({
            "timestamp": datetime.now().isoformat(),
            "level": "info",
            "message": "系统就绪，等待运行"
        })
    else:
        alerts.append({
            "timestamp": datetime.now().isoformat(),
            "level": "warning",
            "message": f"存在未对账订单: {reconciliation.get('open_orders', 0)}"
        })
    
    return alerts


def _get_default_config():
    """获取默认配置"""
    return {
        "capital_base": 1000000,
        "watchlist": ["600519.SH", "000858.SZ", "601318.SH"],
        "max_position_ratio": 0.2,
        "stop_loss_ratio": 0.05,
        "max_daily_loss_ratio": 0.03,
        "allow_new_positions": True,
        "decision_mode": "mock",
        "execution_mode": "full"
    }


def _build_blocked_response(reason):
    """构建阻断响应"""
    return {
        "mode": "shadow",
        "trade_date": datetime.now().strftime("%Y-%m-%d"),
        "last_run_at": None,
        "services": {
            "database": "ok",
            "llm": "unknown",
            "market": "unknown"
        },
        "kill_switch": {
            "active": True
        },
        "config": _get_default_config(),
        "risk": {
            "concentration_ratio": 0.2,
            "active_target_count": 0,
            "open_orders": 0,
            "alerts": [{
                "timestamp": datetime.now().isoformat(),
                "level": "error",
                "message": reason
            }]
        },
        "latest_run": {
            "status": "blocked",
            "steps": [{
                "stage": "blocked",
                "status": "blocked",
                "timestamp": datetime.now().isoformat(),
                "message": reason
            }]
        },
        "history": {
            "decisions": [],
            "orders": [],
            "targets": [],
            "events": []
        }
    }