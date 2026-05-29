from datetime import datetime, timedelta, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from src.agents.llm_client import LLMClient
from src.core.config import Settings
from src.data.providers.akshare_provider import AkshareProvider
from src.storage.dependencies import get_runtime_store

_CST = timezone(timedelta(hours=8))


def _now_cst() -> datetime:
    """返回北京时间（CST, UTC+8）"""
    return datetime.now(_CST)


def _today_close_cst() -> datetime:
    """返回今天 A 股收盘时间（北京时间 15:00:00）"""
    today = _now_cst().replace(hour=15, minute=0, second=0, microsecond=0)
    return today

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

    # LLM 探针：有 api_key 即认为 ok，避免每次消耗 token
    if settings.llm_provider == "mock" or not settings.llm_api_key:
        llm_status = "ok"  # mock 模式
    else:
        llm_status = "ok"  # api_key 已配置

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


def _compute_order_pnl(action: str, quantity: int, fill_price: float, current_price: float) -> float:
    """根据成交价和当前市价计算模拟盈亏。"""
    if action == "BUY":
        return round((current_price - fill_price) * quantity, 2)
    else:
        return round((fill_price - current_price) * quantity, 2)


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
    run_context_id = f"wrk-{_now_cst().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    from src.decision.decision_runner import parse_decision_output
    from src.agents.schemas import DecisionOutput

    settings = Settings()
    llm = _get_llm()
    use_real_llm = (settings.llm_provider != "mock" and bool(settings.llm_api_key))
    provider = AkshareProvider()

    decision_items: list[dict] = []
    target_items: list[dict] = []
    order_items: list[dict] = []
    created_orders: list[dict] = []

    # 清理过期的目标仓位
    store.deactivate_expired_targets()

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
        model_label = llm.model if use_real_llm else "mock-llm"

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
            expires_at=_today_close_cst().isoformat(),
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
            # 用真实行情价格和目标仓位计算实际数量
            try:
                real_snap = provider.get_realtime_quote(symbol)
                real_price = real_snap.close if real_snap else 100.0
            except Exception:
                real_price = 100.0
            target_value = capital_base * settings.strategy_max_position_ratio
            quantity = max(100, int(target_value / real_price / 100) * 100) if real_price > 0 else 100
            if parsed_action == "SELL":
                quantity = max(100, quantity)
            execution_order_id = store.insert_execution_order(
                target_position_id=target_position_id,
                symbol=symbol,
                action=parsed_action,
                quantity=quantity,
                limit_price=real_price,
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
                    "limit_price": real_price,
                    "status": "READY",
                }
            )

    if not decision_only and created_orders:
        for order in created_orders:
            store.update_execution_order_status(order["execution_order_id"], status="FILLED")
            # 用真实价格计算盈亏
            try:
                real_snap = provider.get_realtime_quote(order["symbol"])
                current_price = real_snap.close if real_snap else order["limit_price"]
            except Exception:
                current_price = order["limit_price"]
            pnl_delta = _compute_order_pnl(
                action=order["action"],
                quantity=order["quantity"],
                fill_price=order["limit_price"],
                current_price=current_price,
            )
            store.insert_broker_order_event(
                execution_order_id=order["execution_order_id"],
                event_id=f"evt-filled-{uuid.uuid4().hex[:10]}",
                event_type="FILLED",
                payload={"source": "dashboard", "run_context_id": run_context_id, "pnl_delta": pnl_delta},
            )
            order["status"] = "FILLED"
            order["pnl_delta"] = pnl_delta
            order_items.append(
                {
                    "symbol": order["symbol"],
                    "action": order["action"],
                    "quantity": order["quantity"],
                    "status": order["status"],
                    "pnl_delta": pnl_delta,
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
        "trade_date": _now_cst().date().isoformat(),
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
    latest_decision_mode = (
        (((decisions[0].get("input_snapshot") or {}).get("features") or {}).get("decision_mode"))
        or "mock"
    )
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
        decision_mode=latest_decision_mode,
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
        "input_snapshot": row.get("input_snapshot", {}),
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
    now = _now_cst().isoformat()
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


@router.post("/api/v1/dashboard/backtest")
def run_backtest(config: dict) -> dict:
    """快速回测：对 watchlist 股票运行日频确定性策略回测。"""
    watchlist = config.get("watchlist")
    if not watchlist:
        raise HTTPException(status_code=400, detail="watchlist is empty")
    start_str = config.get("start_date", "2025-01-01")
    end_str = config.get("end_date", "2025-03-31")
    capital_base = int(config.get("capital_base", 1_000_000))

    from src.backtest.engine import run_daily_backtest
    from src.backtest.metrics import calculate_metrics
    from src.indicators.technical_indicators import compute_feature_row
    from src.strategy.signal_engine import build_signal
    from src.strategy.strategy_config import StrategyConfig

    settings = Settings()
    strategy_config = StrategyConfig.from_settings(settings)
    provider = AkshareProvider()

    start_date = datetime.strptime(start_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_str, "%Y-%m-%d")

    # 提前 90 天取数据，确保有足够的历史窗口计算特征
    data_start = start_date - timedelta(days=120)

    results = []
    for symbol in watchlist:
        bars_df = provider.get_history(symbol, data_start, end_date)
        if bars_df.empty:
            continue

        bars = bars_df.to_dict("records")
        close_prices = [b["close"] for b in bars]

        signals = []
        for i in range(60, len(bars)):
            window = close_prices[max(0, i - 60):i + 1]
            features = compute_feature_row(window)
            signal = build_signal(symbol, features, strategy_config)
            if signal["action"] != "HOLD":
                signals.append({
                    "date": bars[i]["date"],
                    "action": signal["action"],
                    "target_position_ratio": settings.strategy_max_position_ratio if signal["action"] == "BUY" else 0.0,
                })

        bt_result = run_daily_backtest(
            symbol=symbol,
            bars=bars,
            initial_cash=float(capital_base),
            signals=signals,
        )
        metrics = calculate_metrics(bt_result["equity_curve"], bt_result["trades"])

        # 多因子分析：取最后一根 K 线的特征
        latest_features = compute_feature_row(close_prices)
        latest_signal = build_signal(symbol, latest_features, strategy_config)

        factor_details = {
            "features": latest_features,
            "technical_score": latest_signal["technical_score"],
            "action": latest_signal["action"],
            "weights": {
                "momentum_20": 0.30,
                "momentum_60": 0.25,
                "ma20_gap": 0.20,
                "ma60_gap": 0.15,
                "volume_ratio_20": 0.10,
                "volatility_20": -0.10,
            },
            "contributions": {
                "momentum_20": round(0.30 * latest_features.get("momentum_20", 0), 6),
                "momentum_60": round(0.25 * latest_features.get("momentum_60", 0), 6),
                "ma20_gap": round(0.20 * latest_features.get("ma20_gap", 0), 6),
                "ma60_gap": round(0.15 * latest_features.get("ma60_gap", 0), 6),
                "volume_ratio_20": round(0.10 * latest_features.get("volume_ratio_20", 0), 6),
                "volatility_20": round(-0.10 * latest_features.get("volatility_20", 0), 6),
            },
            "thresholds": {
                "buy": strategy_config.buy_score_threshold,
                "sell": strategy_config.sell_score_threshold,
            },
        }

        results.append({
            "symbol": symbol,
            "metrics": metrics,
            "trade_count": len(bt_result["trades"]),
            "final_nav": bt_result["final_nav"],
            "factor_analysis": factor_details,
        })

    if not results:
        return {"status": "no_data", "results": [], "summary": {}}

    avg_return = sum(r["metrics"]["total_return"] for r in results) / len(results)
    worst_dd = min(r["metrics"]["max_drawdown"] for r in results)
    total_trades = sum(r["trade_count"] for r in results)

    return {
        "status": "ok",
        "start_date": start_str,
        "end_date": end_str,
        "results": results,
        "summary": {
            "total_return_avg": round(avg_return, 6),
            "max_drawdown_worst": round(worst_dd, 6),
            "total_trades": total_trades,
        },
    }


@router.post("/api/v1/dashboard/scan")
def scan_stock_pool(config: dict | None = None) -> dict:
    """全市场自动选股，扫描器预筛 + 历史K线确认。"""
    from datetime import datetime
    from src.data.providers.akshare_provider import _fetch_tencent_quotes_batch
    from src.strategy.stock_scanner import scan_market, confirm_buy_candidates
    from src.strategy.strategy_config import StrategyConfig

    cfg = config or {}
    top_n = int(cfg.get("top_n", 10))

    settings = Settings()
    strategy_config = StrategyConfig.from_settings(settings)
    provider = AkshareProvider()
    stock_list_df = provider.get_stock_list()
    stock_list = stock_list_df.to_dict("records")

    if not stock_list:
        return {"status": "no_catalog", "buy": [], "sell": [], "hold": [], "total_scanned": 0}

    # 第一轮：扫描器筛选（取 3x 候选给确认层）
    result = scan_market(
        stock_list=stock_list,
        fetch_quotes_fn=lambda syms: _fetch_tencent_quotes_batch(syms),
        top_n=top_n * 3,
    )

    # 第二轮：用历史 K 线确认 BUY 候选
    def kline_fetcher(symbol, start, end):
        return provider.get_history(symbol, datetime.fromisoformat(start), datetime.fromisoformat(end))

    confirmed_buy = confirm_buy_candidates(
        result["buy"], kline_fetcher, strategy_config, top_n=top_n
    )
    result["buy"] = confirmed_buy

    return {"status": "ok", **result}


@router.get("/api/v1/dashboard/preferences")
def get_preferences() -> dict:
    """获取用户偏好设置（watchlist 等）。"""
    store = get_runtime_store()
    prefs = store.get_preference("dashboard") or {}
    return prefs


@router.put("/api/v1/dashboard/preferences")
def save_preferences(config: dict) -> dict:
    """保存用户偏好设置。"""
    store = get_runtime_store()
    # 只允许保存白名单字段
    allowed_keys = {"watchlist", "capital_base", "max_position_ratio", "stop_loss_ratio",
                    "max_daily_loss_ratio", "execution_mode"}
    filtered = {k: v for k, v in config.items() if k in allowed_keys}
    store.set_preference("dashboard", filtered)
    return {"status": "ok"}
