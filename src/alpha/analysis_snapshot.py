from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.alpha.analysis_models import AnalysisSnapshot
from src.indicators.technical_indicators import compute_features_from_bars


def _trend_confirmation(bars: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [float(row["close"]) for row in bars]
    if len(closes) < 61:
        return {"ma20": 0.0, "ma60": 0.0, "reclaimed_ma20": False}
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60
    previous_ma20 = sum(closes[-21:-1]) / 20
    reclaimed = closes[-2] <= previous_ma20 and closes[-1] > ma20
    return {
        "ma20": round(ma20, 6),
        "ma60": round(ma60, 6),
        "reclaimed_ma20": reclaimed,
    }


class AnalysisSnapshotBuilder:
    def __init__(
        self,
        history_loader: Callable[[str], list[dict[str, Any]]],
        fundamental_loader: Callable[[str], dict[str, Any]],
    ) -> None:
        self._history_loader = history_loader
        self._fundamental_loader = fundamental_loader

    def build(
        self,
        *,
        symbol: str,
        lots: list[dict[str, Any]],
        portfolio_market_value: float,
    ) -> AnalysisSnapshot:
        bars = self._history_loader(symbol)
        if not bars or float(bars[-1].get("close", 0) or 0) <= 0:
            raise ValueError(f"no closing price for {symbol}")

        quantity = sum(float(lot["quantity"]) for lot in lots)
        total_cost = sum(float(lot["buy_price"]) * float(lot["quantity"]) for lot in lots)
        weighted_cost = total_cost / quantity
        close = float(bars[-1]["close"])
        market_value = close * quantity
        pnl = market_value - total_cost

        features = compute_features_from_bars(bars)
        features.update(_trend_confirmation(bars))

        missing: list[str] = []
        if features["bar_count"] < 61:
            missing.append("technical_history")

        fundamentals = self._fundamental_loader(symbol)
        if fundamentals.get("status") != "ok":
            missing.append("fundamentals")

        missing.append("news")

        return AnalysisSnapshot(
            symbol=symbol,
            market="us" if symbol.endswith(".US") else "a",
            currency="USD" if symbol.endswith(".US") else "CNY",
            as_of=str(bars[-1].get("date") or bars[-1].get("timestamp"))[:10],
            quantity=quantity,
            weighted_avg_cost=round(weighted_cost, 6),
            close=close,
            market_value=market_value,
            unrealized_pnl=pnl,
            unrealized_pnl_ratio=pnl / total_cost,
            position_ratio=market_value / portfolio_market_value if portfolio_market_value > 0 else 1.0,
            stop_loss_ratio=float(lots[-1].get("stop_loss_ratio", -0.08)),
            take_profit_ratio=float(lots[-1].get("take_profit_ratio", 0.20)),
            technical=features,
            fundamentals=fundamentals,
            news={"status": "unavailable", "items": []},
            data_quality={"status": "partial" if missing else "complete", "missing": missing},
        )
