from dataclasses import dataclass


@dataclass(frozen=True)
class AlphaSignal:
    symbol: str
    score: float
    action: str
    reason: str


class AlphaSignalEngine:
    def __init__(self, buy_threshold: float, sell_threshold: float) -> None:
        self._buy_threshold = buy_threshold
        self._sell_threshold = sell_threshold

    def score_asset(self, symbol: str, candles) -> AlphaSignal:
        closes = candles["close"].astype(float)
        fast_ma = closes.tail(3).mean()
        slow_ma = closes.mean()
        trend = (fast_ma - slow_ma) / slow_ma if slow_ma else 0.0
        momentum = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0] if closes.iloc[0] else 0.0
        score = round(2 * trend + 6 * momentum, 4)
        if score >= self._buy_threshold:
            action = "BUY"
        elif score <= self._sell_threshold:
            action = "SELL"
        else:
            action = "HOLD"
        return AlphaSignal(symbol=symbol, score=score, action=action, reason=f"trend={trend:.4f}, momentum={momentum:.4f}")
