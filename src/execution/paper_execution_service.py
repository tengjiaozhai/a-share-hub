from __future__ import annotations

import uuid
from typing import Any

from src.execution.paper_portfolio import apply_fill, compute_nav


class PaperExecutionService:
    def __init__(self, store, fee_bps: float, slippage_bps: float) -> None:
        self.store = store
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps

    def execute_targets(
        self,
        targets: list[dict[str, Any]],
        initial_state: dict,
        mark_prices: dict[str, float],
        trade_date: str,
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

            execution_order_id = self.store.insert_execution_order(
                target_position_id=target["target_position_id"],
                symbol=target["symbol"],
                action=action,
                quantity=quantity,
                limit_price=price,
            )
            self.store.insert_broker_order_event(
                execution_order_id=execution_order_id,
                event_id=f"evt-submitted-{uuid.uuid4().hex[:10]}",
                event_type="SUBMITTED",
                payload={"source": "paper", "trade_date": trade_date},
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
            self.store.update_execution_order_status(execution_order_id, status="FILLED")
            self.store.insert_broker_order_event(
                execution_order_id=execution_order_id,
                event_id=f"evt-filled-{uuid.uuid4().hex[:10]}",
                event_type="FILLED",
                payload={
                    "source": "paper",
                    "trade_date": trade_date,
                    "fill_price": fill_price,
                    "fee": fee,
                    "pnl_delta": pnl_delta,
                },
            )
            order_items.append({
                "execution_order_id": execution_order_id,
                "symbol": target["symbol"],
                "action": action,
                "quantity": quantity,
                "fill_price": fill_price,
                "fee": fee,
                "pnl_delta": pnl_delta,
                "status": "FILLED",
            })

        nav = compute_nav(state, mark_prices)
        snapshot_id = self.store.insert_account_snapshot(cash=state["cash"], nav=nav, positions=state["positions"])
        return {"status": "ok", "orders": order_items, "snapshot_id": snapshot_id, "cash": state["cash"], "nav": nav}

    def _fill_price(self, action: str, price: float) -> float:
        adjustment = self.slippage_bps / 10_000
        if action == "BUY":
            return round(price * (1 + adjustment), 4)
        return round(price * (1 - adjustment), 4)
