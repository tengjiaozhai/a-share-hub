from __future__ import annotations

from typing import Any

from src.core.market_rules import calculate_lot_quantity, resolve_lot_size


def build_target_position(
    symbol: str,
    action: str,
    capital_base: float,
    max_position_ratio: float,
    watchlist_size: int,
    price: float,
    lot_size: int = 0,
    lot_size_a: int = 100,
    lot_size_us: int = 1,
    current_quantity: int = 0,
    expires_at: str = "",
    market: str | None = None,
) -> dict[str, Any]:
    if watchlist_size <= 0:
        raise ValueError("watchlist_size must be positive")

    resolved_lot_size = resolve_lot_size(
        symbol=symbol,
        lot_size_a=lot_size_a,
        lot_size_us=lot_size_us,
        market=market,
    ) if lot_size == 0 else lot_size

    if action == "BUY":
        target_position_ratio = max_position_ratio / watchlist_size
        target_value = int(capital_base * target_position_ratio)
        quantity = calculate_lot_quantity(target_value, price, resolved_lot_size)
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
        "lot_size": resolved_lot_size,
        "expires_at": expires_at,
    }


def build_target_positions(
    decisions: list[dict],
    prices: dict[str, float],
    capital_base: float,
    max_position_ratio: float,
    lot_size: int = 0,
    lot_size_a: int = 100,
    lot_size_us: int = 1,
    current_positions: dict[str, dict] = {},
    expires_at: str = "",
    market: str | None = None,
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
            lot_size_a=lot_size_a,
            lot_size_us=lot_size_us,
            current_quantity=int(current_position.get("quantity", 0)),
            expires_at=expires_at,
            market=market,
        )
        if target["quantity"] > 0:
            targets.append(target)
    return targets
