from __future__ import annotations

from datetime import date


def can_sell_position_same_day(market: str) -> bool:
    if market == "CN_A":
        return False
    return True


def get_price_limit_ratio(stock_type: str) -> float:
    if stock_type == "ST":
        return 0.05
    return 0.10


def is_tradable(status: str) -> bool:
    return status in {"正常交易", "trading"}


def calculate_lot_quantity(target_value: float, price: float, lot_size: int = 100) -> int:
    if target_value <= 0 or price <= 0 or lot_size <= 0:
        return 0
    raw_quantity = int(target_value / price)
    return raw_quantity // lot_size * lot_size


def is_valid_lot_quantity(action: str, quantity: int, lot_size: int = 100) -> bool:
    if quantity <= 0:
        return False
    if action == "BUY":
        return quantity % lot_size == 0
    return True


def is_sell_allowed(market: str, buy_date: date | None, sell_date: date) -> bool:
    if can_sell_position_same_day(market):
        return True
    if buy_date is None:
        return True
    return sell_date > buy_date


def is_limit_locked(action: str, current_price: float, prev_close: float, limit_ratio: float) -> bool:
    if current_price <= 0 or prev_close <= 0 or limit_ratio <= 0:
        return False
    limit_up = prev_close * (1 + limit_ratio)
    limit_down = prev_close * (1 - limit_ratio)
    if action == "BUY":
        return current_price >= round(limit_up, 2)
    if action == "SELL":
        return current_price <= round(limit_down, 2)
    return False
