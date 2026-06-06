from __future__ import annotations

from src.strategy.strategy_config import StrategyConfig

_WEIGHTS = {
    "momentum_20": 0.30,
    "momentum_60": 0.25,
    "ma20_gap": 0.20,
    "ma60_gap": 0.15,
    "volume_ratio_20": 0.10,
    "volatility_20": -0.10,
}


def compute_factor_contributions(features: dict[str, float]) -> dict[str, float]:
    return {
        name: round(weight * features.get(name, 0.0), 6)
        for name, weight in _WEIGHTS.items()
    }


def compute_technical_score(features: dict[str, float]) -> float:
    return sum(compute_factor_contributions(features).values())


def build_signal(symbol: str, features: dict[str, float], config: StrategyConfig) -> dict:
    score = compute_technical_score(features)
    rsi = features.get("rsi_14", 50.0)
    ma20_gap = features.get("ma20_gap", 0.0)

    if score >= config.buy_score_threshold and 45 <= rsi <= 72:
        action = "BUY"
    elif score <= config.sell_score_threshold or rsi >= 80 or ma20_gap <= -0.05:
        action = "SELL"
    else:
        action = "HOLD"

    return {
        "symbol": symbol,
        "action": action,
        "technical_score": round(score, 6),
        "rsi_14": rsi,
        "features": dict(features),
        "weights": dict(_WEIGHTS),
        "contributions": compute_factor_contributions(features),
        "thresholds": {
            "buy": config.buy_score_threshold,
            "sell": config.sell_score_threshold,
        },
    }
