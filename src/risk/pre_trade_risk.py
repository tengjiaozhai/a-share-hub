from __future__ import annotations

from datetime import date
from typing import Any

from src.core.market_rules import is_sell_allowed, is_valid_lot_quantity


def _blocked(rule_name: str, reason: str, details: dict[str, Any]) -> dict[str, Any]:
    return {"approved": False, "rule_name": rule_name, "reason": reason, "details": details}


def evaluate_risk_gate(
    symbol: str,
    action: str,
    kill_switch: bool,
    available_cash: float,
    requested_value: float,
    current_position_value: float,
    nav: float,
    max_position_ratio: float,
    quantity: int,
    lot_size: int,
    market: str = "CN_A",
    buy_date: date | None = None,
    trade_date: date | None = None,
) -> dict[str, Any]:
    details = {
        "symbol": symbol,
        "action": action,
        "available_cash": available_cash,
        "requested_value": requested_value,
        "current_position_value": current_position_value,
        "nav": nav,
        "max_position_ratio": max_position_ratio,
        "quantity": quantity,
        "lot_size": lot_size,
        "market": market,
        "buy_date": buy_date.isoformat() if buy_date else None,
        "trade_date": trade_date.isoformat() if trade_date else None,
    }
    if kill_switch:
        return _blocked("kill_switch", "kill switch enabled", details)
    if action not in {"BUY", "SELL"}:
        return _blocked("action", "action must be BUY or SELL", details)
    if not is_valid_lot_quantity(action, quantity, lot_size):
        return _blocked("lot_size", "invalid quantity for market lot rule", details)
    if action == "BUY" and requested_value <= 0:
        return _blocked("request_value", "invalid request amount", details)
    if action == "BUY" and requested_value > available_cash:
        return _blocked("cash", "insufficient cash", details)
    if action == "BUY" and nav > 0:
        next_position_ratio = (current_position_value + requested_value) / nav
        if next_position_ratio > max_position_ratio:
            details["next_position_ratio"] = next_position_ratio
            return _blocked("max_position_ratio", "position limit exceeded", details)
    if action == "SELL":
        effective_trade_date = trade_date or date.today()
        if not is_sell_allowed(market, buy_date, effective_trade_date):
            details["trade_date"] = effective_trade_date.isoformat()
            return _blocked("t_plus_one", "same-day A-share sell blocked", details)
    return {"approved": True, "rule_name": "approved", "reason": "approved", "details": details}
