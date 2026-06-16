from __future__ import annotations

from time import perf_counter

from src.execution.paper_execution_service import PaperExecutionService
from src.portfolio.target_planner import build_target_positions
from src.risk.pre_trade_risk import evaluate_risk_gate


class ShadowRunService:
    def __init__(self, store, settings, llm, provider) -> None:
        self.store = store
        self.settings = settings
        self.llm = llm
        self.provider = provider

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
