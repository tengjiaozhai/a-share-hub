from __future__ import annotations


def apply_fill(state: dict, symbol: str, side: str, quantity: int, price: float) -> dict:
    """对账户状态应用一笔成交，返回新状态（不可变风格）。"""
    cash = state["cash"]
    positions = {k: dict(v) for k, v in state["positions"].items()}
    position = dict(positions.get(symbol, {"quantity": 0, "avg_cost": 0.0}))

    if side == "BUY":
        cost = quantity * price
        cash -= cost
        total_qty = position["quantity"] + quantity
        total_cost = position["quantity"] * position["avg_cost"] + cost
        position = {
            "quantity": total_qty,
            "avg_cost": total_cost / total_qty if total_qty > 0 else 0.0,
        }
    else:  # SELL
        cash += quantity * price
        remaining = max(position["quantity"] - quantity, 0)
        position = {"quantity": remaining, "avg_cost": position["avg_cost"]}

    positions[symbol] = position
    return {"cash": cash, "positions": positions}


def compute_nav(state: dict, prices: dict[str, float]) -> float:
    """计算当前账户净值 = 现金 + sum(持仓 * 当前市价)。"""
    nav = state["cash"]
    for symbol, pos in state["positions"].items():
        qty = pos.get("quantity", 0)
        mark_price = prices.get(symbol, pos.get("avg_cost", 0.0))
        nav += qty * mark_price
    return nav
