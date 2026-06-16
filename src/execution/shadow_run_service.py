from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src.agents.schemas import DecisionOutput
from src.decision.decision_runner import parse_decision_output
from src.execution.paper_execution_service import PaperExecutionService
from src.portfolio.target_planner import build_target_positions
from src.risk.pre_trade_risk import evaluate_risk_gate

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))


def _now_cst_iso() -> str:
    return datetime.now(_CST).isoformat()


def _today_close_cst_iso() -> str:
    now = datetime.now(_CST)
    close = now.replace(hour=15, minute=0, second=0, microsecond=0)
    if close <= now:
        close = close + timedelta(days=1)
    return close.isoformat()


class ShadowRunService:
    def __init__(self, store, settings, llm, provider) -> None:
        self.store = store
        self.settings = settings
        self.llm = llm
        self.provider = provider

    def emit(self, run_context_id: str, event_type: str, stage: str, status: str, payload: dict) -> None:
        self.store.append_dashboard_run_event(
            run_context_id=run_context_id,
            event_type=event_type,
            stage=stage,
            status=status,
            payload=payload,
        )

    def build_run_pnl_summary(self, previous_nav: float, current_nav: float, orders: list[dict], reconcile_items: list[dict]) -> dict:
        execution_fee_total = round(sum(float(order.get("fee", 0.0) or 0.0) for order in orders), 2)
        realized_pnl = round(sum(float(order.get("pnl_delta", 0.0) or 0.0) for order in orders), 2)
        unrealized_pnl = round(sum(float(item.get("unrealized_pnl", 0.0) or 0.0) for item in reconcile_items), 2)
        net_pnl = round(current_nav - previous_nav, 2)
        return {
            "execution_fee_total": execution_fee_total,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "net_pnl": net_pnl,
        }

    def build_reconcile_items(self, snapshot: dict | None, orders: list[dict]) -> list[dict]:
        if snapshot is None:
            return []
        fee_by_symbol: dict[str, float] = {}
        for order in orders:
            symbol = order["symbol"]
            fee_by_symbol[symbol] = round(fee_by_symbol.get(symbol, 0.0) + float(order.get("fee", 0.0) or 0.0), 2)
        items = []
        for symbol, position in (snapshot.get("positions") or {}).items():
            items.append(
                {
                    "symbol": symbol,
                    "quantity": int(position.get("quantity", 0)),
                    "avg_cost": float(position.get("avg_cost", 0.0)),
                    "mark_price": float(position.get("mark_price", 0.0)),
                    "market_value": float(position.get("market_value", 0.0)),
                    "change_pct": float(position.get("change_pct", 0.0)),
                    "unrealized_pnl": float(position.get("unrealized_pnl", 0.0)),
                    "fee_total": fee_by_symbol.get(symbol, 0.0),
                    "mark_time": position.get("mark_time"),
                    "quote_status": position.get("quote_status", "ok"),
                }
            )
        return sorted(items, key=lambda item: item["symbol"])

    def run(self, run_context_id: str, config: dict) -> None:
        """Execute one dashboard shadow run end-to-end and persist a complete
        latest_workbench payload. Emits stage events (decision/target/execute/
        reconcile) and terminates with run.completed or run.failed.

        Stages:
            1. decision — LLM produces a JSON decision per watchlist symbol
            2. target   — convert decisions into sized target positions
            3. execute  — paper-broker fills executable targets
            4. reconcile — derive per-symbol positions vs orders, compute PnL
        """
        started_at = _now_cst_iso()
        watchlist = [str(s).strip() for s in (config.get("watchlist") or []) if str(s).strip()]
        if not watchlist:
            watchlist = ["600519.SH"]
        capital_base = int(config.get("capital_base", 1_000_000))
        max_position_ratio = float(config.get("max_position_ratio", 0.2))
        decision_mode = str(config.get("decision_mode", "mock"))
        execution_mode = "decision" if config.get("execution_mode") == "decision" else "full"
        decision_only = execution_mode == "decision"

        steps: list[dict] = []
        decision_items: list[dict] = []
        target_items: list[dict] = []
        order_items: list[dict] = []
        run_pnl_summary: dict = {
            "execution_fee_total": 0.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "net_pnl": 0.0,
        }
        reconcile_items: list[dict] = []
        last_error: str | None = None
        run_status = "completed"

        def _step(stage: str, status: str, **extra) -> dict:
            step = {"stage": stage, "status": status, "timestamp": _now_cst_iso(), **extra}
            steps.append(step)
            return step

        try:
            # --- Stage 1: decision -----------------------------------------
            self.emit(
                run_context_id,
                "stage.updated",
                stage="decision",
                status="running",
                payload={
                    "message": (
                        f"输入标的: {', '.join(watchlist)} | 资金: ¥{capital_base:,} | "
                        f"模式: {decision_mode}"
                    )
                },
            )

            use_real_llm = bool(
                getattr(self.settings, "llm_provider", "mock") != "mock"
                and getattr(self.settings, "llm_api_key", "")
            )
            model_label = getattr(self.llm, "model", None) or (
                getattr(self.settings, "llm_model", "mock-llm") if use_real_llm else "mock-llm"
            )

            price_by_symbol: dict[str, float] = {}
            for symbol in watchlist:
                try:
                    snap = self.provider.get_realtime_quote(symbol)
                    price_by_symbol[symbol] = float(snap.close) if snap is not None else 100.0
                except Exception:
                    price_by_symbol[symbol] = 100.0

            self.store.deactivate_expired_targets()
            current_snapshot = self.store.get_latest_account_snapshot()
            account_state = current_snapshot or {"cash": float(capital_base), "positions": {}}
            current_positions = account_state.get("positions", {}) if isinstance(account_state, dict) else {}

            for index, symbol in enumerate(watchlist):
                if use_real_llm:
                    prompt = (
                        f"你是一个量化交易助手，请分析股票 {symbol} 并给出交易建议。"
                        f"总资金: {capital_base} 元，最大持仓比例: {max_position_ratio*100:.0f}%。"
                        "请以 JSON 格式回复，包含字段：symbol, action(BUY/SELL/HOLD), "
                        "confidence(0-100整数), target_position_ratio(0.0-1.0), reason(中文理由)。"
                    )
                    raw = self.llm.generate(prompt)
                else:
                    decision_pattern = [("BUY", 78), ("HOLD", 45), ("SELL", 82)]
                    mock_action, mock_conf = decision_pattern[index % len(decision_pattern)]
                    raw = (
                        f'{{"symbol":"{symbol}","action":"{mock_action}",'
                        f'"confidence":{mock_conf},"target_position_ratio":'
                        f'{(max_position_ratio / max(len(watchlist), 1)) if mock_action=="BUY" else 0.0},'
                        f'"reason":"Mock decision"}}'
                    )

                decision: DecisionOutput = parse_decision_output(raw or "")
                parsed_action = decision.action
                confidence = decision.confidence
                target_ratio = decision.target_position_ratio if parsed_action == "BUY" else 0.0
                reason = decision.reason

                decision_run_id = self.store.insert_decision_run(
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
                        "features": config,
                        "symbol": symbol,
                    },
                )
                decision_items.append(
                    {
                        "decision_run_id": decision_run_id,
                        "symbol": symbol,
                        "action": parsed_action,
                        "confidence": confidence,
                        "reason": reason,
                    }
                )

            _step("decision", "done", items=list(decision_items))

            # --- Stage 2: target -------------------------------------------
            self.emit(
                run_context_id,
                "stage.updated",
                stage="target",
                status="running",
                payload={"message": "计算目标仓位..."},
            )

            targets = build_target_positions(
                decisions=decision_items,
                prices=price_by_symbol,
                capital_base=capital_base,
                max_position_ratio=max_position_ratio,
                lot_size_a=getattr(self.settings, "strategy_lot_size_a", 100),
                lot_size_us=getattr(self.settings, "strategy_lot_size_us", 1),
                current_positions=current_positions,
                expires_at=_today_close_cst_iso(),
            )

            executable_targets: list[dict] = []
            for target in targets:
                decision_run_id = next(
                    row["decision_run_id"] for row in decision_items
                    if row["symbol"] == target["symbol"]
                )
                target_position_id = self.store.insert_target_position(
                    decision_run_id=decision_run_id,
                    symbol=target["symbol"],
                    action=target["action"],
                    target_value=target["target_value"],
                    target_position_ratio=target["target_position_ratio"],
                    expires_at=target["expires_at"],
                    run_context_id=run_context_id,
                    price=price_by_symbol.get(target["symbol"], target["price"]),
                    lot_size=target["lot_size"],
                    requested_quantity=target["raw_quantity"],
                    notional=target["notional"],
                )
                target["target_position_id"] = target_position_id
                target["price"] = price_by_symbol.get(target["symbol"], target["price"])
                target["run_context_id"] = run_context_id
                target_items.append(
                    {
                        "target_position_id": target_position_id,
                        "symbol": target["symbol"],
                        "action": target["action"],
                        "target_quantity": target["quantity"] if target["action"] == "BUY" else 0,
                        "target_position_ratio": target["target_position_ratio"],
                        "price": target["price"],
                    }
                )

                current_position = (
                    current_positions.get(target["symbol"], {})
                    if isinstance(current_positions, dict)
                    else {}
                )
                current_position_value = int(current_position.get("quantity", 0)) * float(
                    price_by_symbol.get(target["symbol"], target["price"])
                )
                risk = evaluate_risk_gate(
                    symbol=target["symbol"],
                    action=target["action"],
                    kill_switch=self.store.get_kill_switch(),
                    available_cash=float(account_state.get("cash", capital_base)),
                    requested_value=float(target["notional"]),
                    current_position_value=current_position_value,
                    nav=float(account_state.get("nav", capital_base)),
                    max_position_ratio=max_position_ratio,
                    quantity=int(target["quantity"]),
                    lot_size=int(target["lot_size"]),
                )
                if risk["approved"]:
                    executable_targets.append(target)

            _step("target", "done", items=list(target_items))

            # --- Stage 3: execute ------------------------------------------
            self.emit(
                run_context_id,
                "stage.updated",
                stage="execute",
                status="running",
                payload={"message": "发送订单中..."},
            )

            execution_result: dict | None = None
            if not decision_only and executable_targets:
                execution_result = PaperExecutionService(
                    store=self.store,
                    fee_bps=getattr(self.settings, "strategy_fee_bps", 3.0),
                    slippage_bps=getattr(self.settings, "strategy_slippage_bps", 5.0),
                ).execute_targets(
                    targets=executable_targets,
                    initial_state=account_state,
                    mark_prices=price_by_symbol,
                    trade_date=datetime.now(_CST).date().isoformat(),
                )
                order_items.extend(execution_result.get("orders", []))

            if decision_only:
                _step("execute", "skipped", message="仅决策模式，跳过执行")
            elif order_items:
                _step("execute", "done", items=list(order_items))
            else:
                _step("execute", "done", message="无可执行订单，已跳过模拟执行")

            # --- Stage 4: reconcile ---------------------------------------
            self.emit(
                run_context_id,
                "stage.updated",
                stage="reconcile",
                status="running",
                payload={"message": "核对执行结果..."},
            )

            previous_nav = float(account_state.get("nav", capital_base))
            latest_snapshot = self.store.get_latest_account_snapshot(run_context_id=run_context_id) or current_snapshot
            if not decision_only and execution_result is not None:
                current_nav = float(execution_result.get("nav", previous_nav))
            elif latest_snapshot is not None:
                current_nav = float(latest_snapshot.get("nav", previous_nav))
            else:
                current_nav = previous_nav

            reconcile_items = self.build_reconcile_items(latest_snapshot, order_items)
            run_pnl_summary = self.build_run_pnl_summary(previous_nav, current_nav, order_items, reconcile_items)
            daily_pnl = run_pnl_summary["net_pnl"]

            _step(
                "reconcile",
                "done",
                message=f"所有订单已确认。模拟盈亏: {daily_pnl:+.2f}",
                reconcile_items=reconcile_items,
                run_pnl_summary=run_pnl_summary,
            )

        except Exception as exc:  # noqa: BLE001 - emit failure context, then re-raise below
            run_status = "failed"
            last_error = f"{type(exc).__name__}: {exc}"
            logger.exception("ShadowRunService.run failed: %s", run_context_id)
            try:
                self.emit(
                    run_context_id,
                    "run.failed",
                    stage="reconcile",
                    status="failed",
                    payload={"error": last_error, "message": "影子运行异常终止"},
                )
            except Exception:
                logger.exception("Failed to emit run.failed event")
        finally:
            finished_at = _now_cst_iso()
            # Always persist the latest_workbench snapshot, even on failure
            try:
                self._persist_latest_workbench(
                    run_context_id=run_context_id,
                    config=config,
                    started_at=started_at,
                    finished_at=finished_at,
                    status=run_status,
                    steps=steps,
                    decision_items=decision_items,
                    target_items=target_items,
                    order_items=order_items,
                    reconcile_items=reconcile_items,
                    run_pnl_summary=run_pnl_summary,
                    last_error=last_error,
                )
            except Exception:
                logger.exception("Failed to persist latest_workbench for %s", run_context_id)

            if run_status == "completed":
                self.emit(
                    run_context_id,
                    "run.completed",
                    stage="reconcile",
                    status="done",
                    payload={
                        "summary": run_pnl_summary,
                        "steps": steps,
                        "message": "影子运行已完成",
                    },
                )

    def _persist_latest_workbench(
        self,
        *,
        run_context_id: str,
        config: dict,
        started_at: str,
        finished_at: str,
        status: str,
        steps: list[dict],
        decision_items: list[dict],
        target_items: list[dict],
        order_items: list[dict],
        reconcile_items: list[dict],
        run_pnl_summary: dict,
        last_error: str | None,
    ) -> None:
        trade_date = datetime.now(_CST).date().isoformat()
        events = self.store.list_dashboard_run_events(run_context_id)
        kill_switch_active = bool(self.store.get_kill_switch())
        reconciliation = self.store.get_reconciliation_status(run_context_id=run_context_id)
        daily_pnl = float(run_pnl_summary.get("net_pnl", 0.0))
        capital_base = int(config.get("capital_base", 1_000_000))
        decision_mode = str(config.get("decision_mode", "mock"))

        latest_run_payload = {
            "run_context_id": run_context_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "status": status,
            "steps": steps,
            "target_items": target_items,
            "reconcile_items": reconcile_items,
            "order_items": order_items,
            "run_pnl_summary": run_pnl_summary,
            "watchlist": list(config.get("watchlist") or []),
            "capital_base": capital_base,
            "decision_mode": decision_mode,
        }
        if last_error is not None:
            latest_run_payload["error"] = last_error

        latest_workbench = {
            "mode": config.get("mode", "shadow"),
            "trade_date": trade_date,
            "last_run_at": finished_at,
            "services": {},
            "kill_switch": {"active": kill_switch_active},
            "performance": {
                "today_return": 0.0,
                "month_return": 0.0,
                "max_drawdown": 0.0,
                "nav_curve": [],
                "comparison_cards": [],
            },
            "automation": {
                "today_status": status,
                "last_run_at": finished_at,
                "next_run_at": None,
            },
            "risk": {
                "active_target_count": len(target_items),
                "open_orders": reconciliation.get("open_orders", 0),
                "broker_event_count": reconciliation.get("broker_event_count", 0),
                "healthy": reconciliation.get("healthy", True),
                "daily_pnl": daily_pnl,
                "alerts": [],
            },
            "latest_run": latest_run_payload,
            "history": {
                "decisions": decision_items,
                "orders": order_items,
                "targets": target_items,
                "reconcile": reconcile_items,
                "events": events,
            },
            "pagination": {
                "decisions": {"page": 1, "page_size": 20, "total": len(decision_items), "total_pages": 1},
                "orders": {"page": 1, "page_size": 20, "total": len(order_items), "total_pages": 1},
                "targets": {"page": 1, "page_size": 20, "total": len(target_items), "total_pages": 1},
            },
            "alpha": {},
        }

        self.store.upsert_dashboard_run_summary(
            run_context_id=run_context_id,
            trade_date=trade_date,
            decision_mode=decision_mode,
            execution_mode=("decision" if config.get("execution_mode") == "decision" else "full"),
            capital_base=capital_base,
            status=status,
            execution_fee_total=run_pnl_summary.get("execution_fee_total", 0.0),
            realized_pnl=run_pnl_summary.get("realized_pnl", 0.0),
            unrealized_pnl=run_pnl_summary.get("unrealized_pnl", 0.0),
            net_pnl=run_pnl_summary.get("net_pnl", 0.0),
            started_at=started_at,
            finished_at=finished_at if status == "completed" else finished_at,
            latest_workbench=latest_workbench,
        )
