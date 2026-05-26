from datetime import datetime, timedelta
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from src.storage.dependencies import get_runtime_store

router = APIRouter()

_HISTORY_LIMIT = 20


@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    with open("src/api/dashboard.html", "r", encoding="utf-8") as f:
        return f.read()


@router.get("/api/v1/dashboard/workbench")
def get_workbench(store=Depends(get_runtime_store)) -> dict:
    return _build_workbench_payload(store)


@router.post("/api/v1/dashboard/run")
def run_shadow_once(config: dict | None = None, store=Depends(get_runtime_store)) -> dict:
    if store.get_kill_switch():
        return _build_workbench_payload(store)

    payload = config or {}
    watchlist = payload.get("watchlist") or ["600519.SH"]
    capital_base = int(payload.get("capital_base", 1_000_000))
    max_position_ratio = float(payload.get("max_position_ratio", 0.2))
    execution_mode = payload.get("execution_mode", "full")

    ratio_per_symbol = max_position_ratio / len(watchlist)
    target_value_per_symbol = int(capital_base * ratio_per_symbol)
    run_context_id = f"wrk-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    for symbol in watchlist:
        parsed_action = "BUY"
        decision_run_id = store.insert_decision_run(
            symbol=symbol,
            prompt_hash=f"dashboard-{run_context_id}",
            model_name="mock-llm",
            raw_output=f'{{"symbol":"{symbol}","action":"{parsed_action}","confidence":80}}',
            parsed_action=parsed_action,
            confidence=80,
            target_position_ratio=ratio_per_symbol,
            reason="dashboard shadow run",
            input_snapshot={
                "market_context": {"mode": "shadow", "run_context_id": run_context_id},
                "features": payload,
                "symbol": symbol,
            },
        )
        target_position_id = store.insert_target_position(
            decision_run_id=decision_run_id,
            symbol=symbol,
            action=parsed_action,
            target_value=target_value_per_symbol,
            target_position_ratio=ratio_per_symbol,
            expires_at=(datetime.utcnow() + timedelta(hours=1)).isoformat(),
        )

        if execution_mode != "decision":
            execution_order_id = store.insert_execution_order(
                target_position_id=target_position_id,
                symbol=symbol,
                action=parsed_action,
                quantity=100,
                limit_price=100.0,
            )
            store.insert_broker_order_event(
                execution_order_id=execution_order_id,
                event_id=f"evt-{uuid.uuid4().hex[:12]}",
                event_type="SUBMITTED",
                payload={"source": "dashboard", "run_context_id": run_context_id},
            )

    return _build_workbench_payload(store)


def _build_workbench_payload(store) -> dict:
    reconciliation = store.get_reconciliation_status()
    decision_rows = store.list_decision_runs(limit=_HISTORY_LIMIT)
    target_rows = store.list_active_target_positions(limit=_HISTORY_LIMIT)
    order_rows = store.list_execution_orders(limit=_HISTORY_LIMIT)

    decisions = [_serialize_decision_row(row) for row in decision_rows]
    targets = [_serialize_target_row(row) for row in target_rows]
    orders = [_serialize_order_row(row) for row in order_rows]

    latest_run = _build_latest_run(decisions=decisions, targets=targets, orders=orders)

    return {
        "mode": "shadow",
        "trade_date": datetime.utcnow().date().isoformat(),
        "last_run_at": latest_run.get("finished_at") or latest_run.get("started_at"),
        "services": {
            "database": "ok",
            "llm": "unknown",
            "market": "unknown",
        },
        "kill_switch": {"active": store.get_kill_switch()},
        "risk": {
            "active_target_count": len(targets),
            "open_orders": reconciliation.get("open_orders", 0),
            "broker_event_count": reconciliation.get("broker_event_count", 0),
            "healthy": reconciliation.get("healthy", False),
        },
        "latest_run": latest_run,
        "history": {
            "decisions": decisions,
            "orders": orders,
            "targets": targets,
            "events": _list_recent_events(store, limit=_HISTORY_LIMIT),
        },
    }


def _build_latest_run(decisions: list[dict], targets: list[dict], orders: list[dict]) -> dict:
    if not decisions and not targets and not orders:
        return {"status": "idle", "steps": []}

    steps = []
    if decisions:
        steps.append(
            {
                "stage": "decision",
                "status": "done",
                "timestamp": decisions[0].get("created_at"),
                "items": [
                    {
                        "symbol": row.get("symbol"),
                        "action": row.get("action"),
                        "confidence": row.get("confidence"),
                        "reason": row.get("reason"),
                    }
                    for row in decisions[:5]
                ],
            }
        )
    if targets:
        steps.append(
            {
                "stage": "target",
                "status": "done",
                "timestamp": targets[0].get("created_at"),
                "items": [
                    {
                        "symbol": row.get("symbol"),
                        "action": row.get("action"),
                        "target_value": row.get("target_value"),
                    }
                    for row in targets[:5]
                ],
            }
        )
    if orders:
        steps.append(
            {
                "stage": "execute",
                "status": "done",
                "timestamp": orders[0].get("created_at"),
                "items": [
                    {
                        "symbol": row.get("symbol"),
                        "action": row.get("action"),
                        "quantity": row.get("quantity"),
                        "limit_price": row.get("limit_price"),
                        "status": row.get("status"),
                    }
                    for row in orders[:5]
                ],
            }
        )

    started_candidates = [
        row.get("created_at")
        for row in [*(decisions[:1]), *(targets[:1]), *(orders[:1])]
        if row.get("created_at")
    ]
    started_at = min(started_candidates) if started_candidates else None
    finished_at = max(started_candidates) if started_candidates else None

    return {
        "run_context_id": decisions[0].get("decision_run_id") if decisions else None,
        "started_at": started_at,
        "finished_at": finished_at,
        "status": "completed",
        "steps": steps,
    }


def _serialize_decision_row(row: dict) -> dict:
    parsed_action = row.get("parsed_action")
    return {
        "decision_run_id": row.get("decision_run_id"),
        "symbol": row.get("symbol"),
        "parsed_action": parsed_action,
        "action": _map_action(parsed_action),
        "confidence": row.get("confidence"),
        "reason": row.get("reason", ""),
        "created_at": row.get("created_at"),
    }


def _serialize_target_row(row: dict) -> dict:
    return {
        "target_position_id": row.get("target_position_id"),
        "decision_run_id": row.get("decision_run_id"),
        "symbol": row.get("symbol"),
        "action": row.get("action"),
        "target_value": row.get("target_value"),
        "target_position_ratio": row.get("target_position_ratio"),
        "status": row.get("status"),
        "expires_at": row.get("expires_at"),
        "created_at": row.get("created_at"),
    }


def _serialize_order_row(row: dict) -> dict:
    return {
        "execution_order_id": row.get("execution_order_id"),
        "target_position_id": row.get("target_position_id"),
        "symbol": row.get("symbol"),
        "action": row.get("action"),
        "quantity": row.get("quantity"),
        "limit_price": row.get("limit_price"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
    }


def _map_action(parsed_action: str | None) -> str:
    if not parsed_action:
        return "HOLD"
    normalized = str(parsed_action).upper()
    if normalized in {"BUY", "SELL", "HOLD"}:
        return normalized
    if normalized in {"NONE", "NO_ACTION", "WAIT"}:
        return "HOLD"
    return normalized


def _list_recent_events(store, limit: int) -> list[dict]:
    kill_switch_events = store.list_kill_switch_events(limit=limit)
    broker_events = store.list_broker_events(limit=limit)

    events: list[dict] = []
    for row in kill_switch_events:
        events.append(
            {
                "type": "kill_switch_event",
                "kill_switch_event_id": row.get("kill_switch_event_id"),
                "active": row.get("active"),
                "reason": row.get("reason"),
                "created_at": row.get("created_at"),
            }
        )
    for row in broker_events:
        events.append(
            {
                "type": "broker_event",
                "event_id": row.get("event_id"),
                "order_id": row.get("order_id"),
                "event_type": row.get("event_type"),
                "payload": row.get("payload"),
                "created_at": row.get("created_at"),
            }
        )

    return sorted(events, key=lambda item: item.get("created_at") or "", reverse=True)[:limit]
