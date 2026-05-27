from __future__ import annotations

from src.strategy.strategy_config import StrategyConfig


def compute_technical_score(features: dict[str, float]) -> float:
    """量化评分公式（确定性，与 signal_engine 描述一致）。"""
    return (
        0.30 * features.get("momentum_20", 0.0)
        + 0.25 * features.get("momentum_60", 0.0)
        + 0.20 * features.get("ma20_gap", 0.0)
        + 0.15 * features.get("ma60_gap", 0.0)
        + 0.10 * features.get("volume_ratio_20", 0.0)
        - 0.10 * features.get("volatility_20", 0.0)
    )


def build_signal(symbol: str, features: dict[str, float], config: StrategyConfig) -> dict:
    """根据特征和策略配置输出确定性信号。

    BUY:  评分 >= buy_score_threshold 且 45 <= rsi_14 <= 72
    SELL: 评分 <= sell_score_threshold 或 rsi_14 >= 80 或 ma20_gap <= -0.05
    HOLD: 其余情况
    """
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
    }
