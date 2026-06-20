from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from src.execution.paper_portfolio import apply_fill, compute_nav

_CST = timezone(timedelta(hours=8))


def _now_cst_iso() -> str:
    return datetime.now(_CST).isoformat()


class PaperExecutionService:
    def __init__(self, store, fee_bps: float, slippage_bps: float) -> None:
        self.store = store
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps

    def execute_targets(
        self,
        user_id: str,
        targets: list[dict[str, Any]],
        initial_state: dict,
        mark_prices: dict[str, float],
        quote_meta_by_symbol: dict[str, dict[str, Any]] | None = None,
        trade_date: str = "",
    ) -> dict[str, Any]:
        state = {"cash": float(initial_state["cash"]), "positions": dict(initial_state.get("positions", {}))}
        order_items = []

        for target in targets:
            action = target["action"]
            price = float(target["price"])
            fill_price = self._fill_price(action, price)
            quantity = int(target["quantity"])
            notional = quantity * fill_price
            fee = round(notional * self.fee_bps / 10_000, 2)
            submitted_at = _now_cst_iso()

            execution_order_id = self.store.insert_execution_order(
                                target_position_id=target["target_position_id"],
                run_context_id=target.get("run_context_id"),
                symbol=target["symbol"],
                action=action,
                quantity=quantity,
                limit_price=price,
                status="SUBMITTED",
                status_code="SUBMITTED",
                status_reason="paper_submitted",
                submitted_at=submitted_at,
                slippage_bps=self.slippage_bps,
            )
            self.store.insert_broker_order_event(
                execution_order_id=execution_order_id,
                run_context_id=target.get("run_context_id"),
                event_id=f"evt-submitted-{uuid.uuid4().hex[:10]}",
                event_type="SUBMITTED",
                payload={"source": "paper", "trade_date": trade_date, "submitted_at": submitted_at},
            )

            fill_state = apply_fill(
                state=state,
                symbol=target["symbol"],
                side=action,
                quantity=quantity,
                price=fill_price,
                fee=fee,
                trade_date=trade_date,
            )
            state = {"cash": fill_state["cash"], "positions": fill_state["positions"]}
            pnl_delta = fill_state["realized_pnl"]
            filled_at = _now_cst_iso()
            self.store.update_execution_order_status(
                execution_order_id=execution_order_id,
                status="FILLED",
                status_code="FILLED",
                status_reason="paper_filled",
                filled_quantity=quantity,
                fill_price=fill_price,
                fee=fee,
                pnl_delta=pnl_delta,
                filled_at=filled_at,
                last_event_at=filled_at,
            )
            self.store.insert_broker_order_event(
                execution_order_id=execution_order_id,
                run_context_id=target.get("run_context_id"),
                event_id=f"evt-filled-{uuid.uuid4().hex[:10]}",
                event_type="FILLED",
                payload={
                    "source": "paper",
                    "trade_date": trade_date,
                    "fill_price": fill_price,
                    "filled_quantity": quantity,
                    "fee": fee,
                    "pnl_delta": pnl_delta,
                    "filled_at": filled_at,
                },
            )
            order_items.append(
                {
                    "execution_order_id": execution_order_id,
                    "target_position_id": target["target_position_id"],
                    "run_context_id": target.get("run_context_id"),
                    "symbol": target["symbol"],
                    "action": action,
                    "quantity": quantity,
                    "filled_quantity": quantity,
                    "limit_price": price,
                    "fill_price": fill_price,
                    "fee": fee,
                    "pnl_delta": pnl_delta,
                    "status": "FILLED",
                    "status_code": "FILLED",
                    "status_reason": "paper_filled",
                    "submitted_at": submitted_at,
                    "filled_at": filled_at,
                }
            )

        nav = compute_nav(state, mark_prices)
        positions = self._decorate_positions(state["positions"], mark_prices, quote_meta_by_symbol or {})
        snapshot_id = self.store.insert_account_snapshot(
                        cash=state["cash"],
            nav=nav,
            positions=positions,
            run_context_id=targets[0].get("run_context_id") if targets else "wrk-empty",
        )
        return {"status": "ok", "orders": order_items, "snapshot_id": snapshot_id, "cash": state["cash"], "nav": nav}

    def _decorate_positions(
        self,
        positions: dict[str, dict[str, Any]],
        mark_prices: dict[str, float],
        quote_meta_by_symbol: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        enriched: dict[str, dict[str, Any]] = {}
        for symbol, position in positions.items():
            quantity = int(position.get("quantity", 0))
            avg_cost = float(position.get("avg_cost", 0.0))
            mark_price = float(mark_prices.get(symbol, avg_cost))
            market_value = round(quantity * mark_price, 2)
            cost_basis = round(quantity * avg_cost, 2)
            unrealized_pnl = round(market_value - cost_basis, 2)
            change_pct = round((mark_price - avg_cost) / avg_cost, 6) if avg_cost else 0.0
            quote_meta = quote_meta_by_symbol.get(symbol, {})
            enriched[symbol] = {
                **position,
                "mark_price": mark_price,
                "market_value": market_value,
                "cost_basis": cost_basis,
                "unrealized_pnl": unrealized_pnl,
                "change_pct": change_pct,
                "mark_time": quote_meta.get("as_of"),
                "quote_status": quote_meta.get("status", "ok"),
            }
        return enriched

    def _fill_price(self, action: str, price: float) -> float:
        adjustment = self.slippage_bps / 10_000
        if action == "BUY":
            return round(price * (1 + adjustment), 4)
        return round(price * (1 - adjustment), 4)
