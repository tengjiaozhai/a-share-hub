from __future__ import annotations


def apply_fill(
    state: dict,
    symbol: str,
    side: str,
    quantity: int,
    price: float,
    fee: float = 0.0,
    trade_date: str = "",
) -> dict:
    cash = float(state["cash"])
    positions = {key: dict(value) for key, value in state.get("positions", {}).items()}
    position = dict(positions.get(symbol, {"quantity": 0, "avg_cost": 0.0, "buy_date": ""}))
    realized_pnl = 0.0

    if side == "BUY":
        cost = quantity * price
        cash -= cost + fee
        total_qty = int(position.get("quantity", 0)) + quantity
        total_cost = int(position.get("quantity", 0)) * float(position.get("avg_cost", 0.0)) + cost
        position = {
            "quantity": total_qty,
            "avg_cost": total_cost / total_qty if total_qty > 0 else 0.0,
            "buy_date": trade_date,
        }
    elif side == "SELL":
        held_qty = int(position.get("quantity", 0))
        if quantity > held_qty:
            raise ValueError("sell quantity exceeds current position")
        proceeds = quantity * price
        realized_pnl = (price - float(position.get("avg_cost", 0.0))) * quantity - fee
        cash += proceeds - fee
        remaining = held_qty - quantity
        position = {
            "quantity": remaining,
            "avg_cost": float(position.get("avg_cost", 0.0)) if remaining > 0 else 0.0,
            "buy_date": position.get("buy_date", ""),
        }
    else:
        raise ValueError("side must be BUY or SELL")

    positions[symbol] = position
    return {"cash": round(cash, 2), "positions": positions, "realized_pnl": round(realized_pnl, 2)}


def compute_nav(state: dict, prices: dict[str, float]) -> float:
    nav = float(state["cash"])
    for symbol, pos in state.get("positions", {}).items():
        qty = int(pos.get("quantity", 0))
        mark_price = float(prices.get(symbol, pos.get("avg_cost", 0.0)))
        nav += qty * mark_price
    return round(nav, 2)
