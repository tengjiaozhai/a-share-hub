from datetime import datetime, timedelta
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from src.agents.llm_client import LLMClient
from src.core.config import Settings
from src.data.providers.akshare_provider import AkshareProvider
from src.storage.dependencies import get_runtime_store

_llm_client: LLMClient | None = None
_akshare: AkshareProvider | None = None


def _get_llm() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def _probe_services() -> dict:
    """探测 LLM 和行情状态，返回 ok / error / unknown"""
    settings = Settings()

    # LLM 探针：只要配置了 api_key 就认为 ok，避免每次都消耗 token
    if settings.llm_provider == "mock" or not settings.llm_api_key:
        llm_status = "ok"  # mock 模式始终绿
    else:
        try:
            import httpx
            r = httpx.get(
                settings.llm_base_url.rstrip("/") + "/models",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                timeout=5.0,
            )
            llm_status = "ok" if r.status_code == 200 else "error"
        except Exception:
            llm_status = "error"

    # 行情探针：检查 akshare 是否可导入
    if settings.market_data_provider == "mock":
        market_status = "ok"
    else:
        global _akshare
        if _akshare is None:
            _akshare = AkshareProvider()
        market_status = "ok" if _akshare.is_available() else "error"

    return {"database": "ok", "llm": llm_status, "market": market_status}

router = APIRouter()

_HISTORY_LIMIT = 20
_PAPER_DAILY_PNL = 1250.0


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
    watchlist = [str(symbol).strip() for symbol in (payload.get("watchlist") or ["600519.SH"]) if str(symbol).strip()]
    if not watchlist:
        watchlist = ["600519.SH"]
    capital_base = int(payload.get("capital_base", 1_000_000))
    max_position_ratio = float(payload.get("max_position_ratio", 0.2))
    execution_mode = "decision" if payload.get("execution_mode") == "decision" else "full"
    decision_only = execution_mode == "decision"

    ratio_per_symbol = max_position_ratio / len(watchlist)
    target_value_per_symbol = int(capital_base * ratio_per_symbol)
    run_context_id = f"wrk-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    from src.decision.decision_runner import parse_decision_output
    from src.agents.schemas import DecisionOutput

    settings = Settings()
    llm = _get_llm()
    use_real_llm = (settings.llm_provider != "mock" and bool(settings.llm_api_key))

    decision_items: list[dict] = []
    target_items: list[dict] = []
    order_items: list[dict] = []
    created_orders: list[dict] = []

    for index, symbol in enumerate(watchlist):
        # 尝试调用真实 LLM，失败则降级到 mock 决策模式
        if use_real_llm:
            prompt = (
                f"你是一个A股量化交易助手，请分析股票 {symbol} 并给出交易建议。"
                f"总资金: {capital_base} 元，最大持仓比例: {max_position_ratio*100:.0f}%。"
                "请以 JSON 格式回复，包含字段：symbol, action(BUY/SELL/HOLD), "
                "confidence(0-100整数), target_position_ratio(0.0-1.0), reason(中文理由)。"
            )
            raw = llm.generate(prompt)
        else:
            decision_pattern = [("BUY", 78), ("HOLD", 45), ("SELL", 82)]
            mock_action, mock_conf = decision_pattern[index % len(decision_pattern)]
            raw = (
                f'{{"symbol":"{symbol}","action":"{mock_action}",'
                f'"confidence":{mock_conf},"target_position_ratio":{ratio_per_symbol if mock_action=="BUY" else 0.0},'
                f'"reason":"Mock decision"}}'
            )

        decision: DecisionOutput = parse_decision_output(raw or "")
        parsed_action = decision.action
        confidence = decision.confidence
        target_ratio = decision.target_position_ratio if parsed_action == "BUY" else 0.0
        reason = decision.reason
        model_label = settings.llm_model if use_real_llm else "mock-llm"

        decision_run_id = store.insert_decision_run(
            symbol=symbol,
            prompt_hash=f"dashboard-{run_context_id}",
            model_name=model_label,
            raw_output=raw or "",
            parsed_action=parsed_action,
            confidence=confidence,
            target_position_ratio=target_ratio,
            reason=reason,
            input_snapshot={
                "market_context": {"mode": "shadow", "run_context_id": run_context_id},
                "features": payload,
                "symbol": symbol,
            },
        )
        decision_items.append(
            {
                "symbol": symbol,
                "action": parsed_action,
                "confidence": confidence,
                "reason": reason,
            }
        )

        if parsed_action == "HOLD":
            continue

        target_value = target_value_per_symbol if parsed_action == "BUY" else 0
        target_position_ratio = ratio_per_symbol if parsed_action == "BUY" else 0.0
        target_quantity = target_value_per_symbol // 1000 if parsed_action == "BUY" else 0
        target_position_id = store.insert_target_position(
            decision_run_id=decision_run_id,
            symbol=symbol,
            action=parsed_action,
            target_value=target_value,
            target_position_ratio=target_position_ratio,
            expires_at=(datetime.utcnow() + timedelta(hours=1)).isoformat(),
        )
        target_items.append(
            {
                "symbol": symbol,
                "target_quantity": target_quantity if parsed_action == "BUY" else "0 (清仓)",
                "target_position_ratio": target_position_ratio,
                "action": parsed_action,
            }
        )

        if not decision_only:
            quantity = 200 if parsed_action == "BUY" else 300
            execution_order_id = store.insert_execution_order(
                target_position_id=target_position_id,
                symbol=symbol,
                action=parsed_action,
                quantity=quantity,
                limit_price=100.0,
            )
            store.insert_broker_order_event(
                execution_order_id=execution_order_id,
                event_id=f"evt-submitted-{uuid.uuid4().hex[:10]}",
                event_type="SUBMITTED",
                payload={"source": "dashboard", "run_context_id": run_context_id},
            )
            created_orders.append(
                {
                    "execution_order_id": execution_order_id,
                    "symbol": symbol,
                    "action": parsed_action,
                    "quantity": quantity,
                    "status": "READY",
                }
            )

    if not decision_only and created_orders:
        pnl_deltas = _allocate_pnl_deltas(total_pnl=_PAPER_DAILY_PNL, item_count=len(created_orders))
        for order, pnl_delta in zip(created_orders, pnl_deltas):
            store.update_execution_order_status(order["execution_order_id"], status="FILLED")
            store.insert_broker_order_event(
                execution_order_id=order["execution_order_id"],
                event_id=f"evt-filled-{uuid.uuid4().hex[:10]}",
                event_type="FILLED",
                payload={"source": "dashboard", "run_context_id": run_context_id, "pnl_delta": pnl_delta},
            )
            order["status"] = "FILLED"
            order_items.append(
                {
                    "symbol": order["symbol"],
                    "action": order["action"],
                    "quantity": order["quantity"],
                    "status": order["status"],
                }
            )

    daily_pnl = store.sum_daily_pnl()
    latest_run = _build_run_timeline(
        run_context_id=run_context_id,
        watchlist=watchlist,
        capital_base=capital_base,
        decision_mode=payload.get("decision_mode", "mock"),
        decision_items=decision_items,
        target_items=target_items,
        order_items=order_items,
        decision_only=decision_only,
        daily_pnl=daily_pnl,
    )

    return _build_workbench_payload(store, latest_run_override=latest_run)


def _build_workbench_payload(store, latest_run_override: dict | None = None) -> dict:
    reconciliation = store.get_reconciliation_status()
    decision_rows = store.list_decision_runs(limit=_HISTORY_LIMIT)
    target_rows = store.list_active_target_positions(limit=_HISTORY_LIMIT)
    order_rows = store.list_execution_orders(limit=_HISTORY_LIMIT)

    decisions = [_serialize_decision_row(row) for row in decision_rows]
    targets = [_serialize_target_row(row) for row in target_rows]
    orders = [_serialize_order_row(row) for row in order_rows]
    daily_pnl = store.sum_daily_pnl()

    latest_run = latest_run_override or _build_latest_run(
        decisions=decisions,
        targets=targets,
        orders=orders,
        daily_pnl=daily_pnl,
    )

    return {
        "mode": "shadow",
        "trade_date": datetime.utcnow().date().isoformat(),
        "last_run_at": latest_run.get("finished_at") or latest_run.get("started_at"),
        "services": _probe_services(),
        "kill_switch": {"active": store.get_kill_switch()},
        "risk": {
            "active_target_count": len(targets),
            "open_orders": reconciliation.get("open_orders", 0),
            "broker_event_count": reconciliation.get("broker_event_count", 0),
            "healthy": reconciliation.get("healthy", False),
            "daily_pnl": daily_pnl,
        },
        "latest_run": latest_run,
        "history": {
            "decisions": decisions,
            "orders": orders,
            "targets": targets,
            "events": _list_recent_events(store, limit=_HISTORY_LIMIT),
        },
    }


def _build_latest_run(decisions: list[dict], targets: list[dict], orders: list[dict], daily_pnl: float) -> dict:
    if not decisions and not targets and not orders:
        return {"status": "idle", "steps": []}

    latest_prompt_hash = decisions[0].get("prompt_hash")
    if latest_prompt_hash:
        run_decisions = [row for row in decisions if row.get("prompt_hash") == latest_prompt_hash]
    else:
        run_decisions = decisions[:1]
    run_decisions = sorted(run_decisions, key=lambda row: row.get("created_at") or "")

    run_decision_ids = {row.get("decision_run_id") for row in run_decisions}
    run_targets = [row for row in targets if row.get("decision_run_id") in run_decision_ids]
    run_targets = sorted(run_targets, key=lambda row: row.get("created_at") or "")
    run_target_ids = {row.get("target_position_id") for row in run_targets}
    run_orders = [row for row in orders if row.get("target_position_id") in run_target_ids]
    run_orders = sorted(run_orders, key=lambda row: row.get("created_at") or "")

    decision_items = [
        {
            "symbol": row.get("symbol"),
            "action": row.get("action"),
            "confidence": row.get("confidence"),
            "reason": row.get("reason"),
        }
        for row in run_decisions[:5]
    ]
    target_items = [
        {
            "symbol": row.get("symbol"),
            "target_quantity": _derive_target_quantity(row.get("target_value"), row.get("action")),
            "target_position_ratio": row.get("target_position_ratio"),
            "action": row.get("action"),
        }
        for row in run_targets[:5]
    ]
    order_items = [
        {
            "symbol": row.get("symbol"),
            "action": row.get("action"),
            "quantity": row.get("quantity"),
            "status": row.get("status"),
        }
        for row in run_orders[:5]
    ]
    decision_only = len(order_items) == 0
    run_context_id = _extract_run_context_id(latest_prompt_hash) or run_decisions[0].get("decision_run_id")

    latest_run = _build_run_timeline(
        run_context_id=run_context_id,
        watchlist=[row.get("symbol") for row in run_decisions if row.get("symbol")],
        capital_base=1_000_000,
        decision_mode="mock",
        decision_items=decision_items,
        target_items=target_items,
        order_items=order_items,
        decision_only=decision_only,
        daily_pnl=daily_pnl,
    )

    started_candidates = [
        row.get("created_at")
        for row in [*(run_decisions[:1]), *(run_targets[:1]), *(run_orders[:1])]
        if row.get("created_at")
    ]
    if started_candidates:
        latest_run["started_at"] = min(started_candidates)
        latest_run["finished_at"] = max(started_candidates)
    return latest_run


def _serialize_decision_row(row: dict) -> dict:
    parsed_action = row.get("parsed_action")
    return {
        "decision_run_id": row.get("decision_run_id"),
        "prompt_hash": row.get("prompt_hash"),
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
        "target_quantity": _derive_target_quantity(row.get("target_value"), row.get("action")),
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


def _extract_run_context_id(prompt_hash: str | None) -> str | None:
    if not prompt_hash:
        return None
    prefix = "dashboard-"
    return prompt_hash[len(prefix):] if prompt_hash.startswith(prefix) else prompt_hash


def _derive_target_quantity(target_value: int | None, action: str | None) -> int | str:
    if action == "SELL":
        return "0 (清仓)"
    if not target_value:
        return 0
    return int(target_value // 1000)


def _allocate_pnl_deltas(total_pnl: float, item_count: int) -> list[float]:
    if item_count <= 0:
        return []
    total_cents = int(round(total_pnl * 100))
    base = total_cents // item_count
    remainder = total_cents % item_count
    cents = [base + (1 if idx < remainder else 0) for idx in range(item_count)]
    return [round(value / 100.0, 2) for value in cents]


def _format_pnl_label(daily_pnl: float) -> str:
    sign = "+" if daily_pnl >= 0 else "-"
    amount = abs(daily_pnl)
    return f"{sign}¥{amount:,.0f}"


def _build_run_timeline(
    run_context_id: str | None,
    watchlist: list[str],
    capital_base: int,
    decision_mode: str,
    decision_items: list[dict],
    target_items: list[dict],
    order_items: list[dict],
    decision_only: bool,
    daily_pnl: float,
) -> dict:
    now = datetime.utcnow().isoformat()
    steps = [
        {
            "stage": "decision",
            "status": "running",
            "timestamp": now,
            "message": f"输入标的: {', '.join(watchlist)} | 资金: ¥{capital_base:,} | 模式: {decision_mode}",
        },
        {
            "stage": "decision",
            "status": "done",
            "timestamp": now,
            "items": decision_items,
        },
        {
            "stage": "target",
            "status": "running",
            "timestamp": now,
            "message": "计算中...",
        },
        {
            "stage": "target",
            "status": "done",
            "timestamp": now,
            "items": target_items,
        },
    ]

    if decision_only:
        steps.append(
            {
                "stage": "reconcile",
                "status": "done",
                "timestamp": now,
                "message": "仅决策模式，跳过执行",
            }
        )
    else:
        steps.extend(
            [
                {
                    "stage": "execute",
                    "status": "running",
                    "timestamp": now,
                    "message": "发送订单中...",
                },
                {
                    "stage": "execute",
                    "status": "done",
                    "timestamp": now,
                    "items": order_items,
                },
                {
                    "stage": "reconcile",
                    "status": "running",
                    "timestamp": now,
                    "message": "核对执行结果...",
                },
                {
                    "stage": "reconcile",
                    "status": "done",
                    "timestamp": now,
                    "message": f"所有订单已确认，持仓已更新。模拟盈亏: {_format_pnl_label(daily_pnl)}",
                },
            ]
        )

    return {
        "run_context_id": run_context_id,
        "started_at": now,
        "finished_at": now,
        "status": "completed",
        "steps": steps,
    }
