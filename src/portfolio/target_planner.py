from __future__ import annotations

from typing import Any

from src.core.market_rules import calculate_lot_quantity


def build_target_position(
    symbol: str,
    action: str,
    capital_base: float,
    max_position_ratio: float,
    watchlist_size: int,
    price: float,
    lot_size: int,
    current_quantity: int = 0,
    expires_at: str = "",
) -> dict[str, Any]:
    if watchlist_size <= 0:
        raise ValueError("watchlist_size must be positive")

    if action == "BUY":
        target_position_ratio = max_position_ratio / watchlist_size
        target_value = int(capital_base * target_position_ratio)
        quantity = calculate_lot_quantity(target_value, price, lot_size)
        notional = int(quantity * price)
    elif action == "SELL":
        target_position_ratio = 0.0
        target_value = 0
        quantity = max(int(current_quantity), 0)
        notional = int(quantity * price)
    else:
        target_position_ratio = 0.0
        target_value = 0
        quantity = 0
        notional = 0

    return {
        "symbol": symbol,
        "action": action,
        "target_value": target_value,
        "target_position_ratio": target_position_ratio,
        "quantity": quantity,
        "notional": notional,
        "price": price,
        "expires_at": expires_at,
    }


def build_target_positions(
    decisions: list[dict],
    prices: dict[str, float],
    capital_base: float,
    max_position_ratio: float,
    lot_size: int,
    current_positions: dict[str, dict],
    expires_at: str = "",
) -> list[dict[str, Any]]:
    active_decisions = [row for row in decisions if row.get("action") in {"BUY", "SELL"}]
    watchlist_size = max(len(decisions), 1)
    targets = []
    for row in active_decisions:
        symbol = row["symbol"]
        current_position = current_positions.get(symbol, {})
        target = build_target_position(
            symbol=symbol,
            action=row["action"],
            capital_base=capital_base,
            max_position_ratio=max_position_ratio,
            watchlist_size=watchlist_size,
            price=prices[symbol],
            lot_size=lot_size,
            current_quantity=int(current_position.get("quantity", 0)),
            expires_at=expires_at,
        )
        if target["quantity"] > 0:
            targets.append(target)
    return targets
