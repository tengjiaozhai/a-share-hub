from __future__ import annotations

import math
from typing import List, Dict


def compute_feature_row(close_prices: List[float], volumes: List[float] | None = None) -> Dict[str, float]:
    """计算技术特征，返回 6 个量化特征字段。

    需要至少 60 根 K 线，不足时全部返回中性默认值。

    返回字段：
        ma20_gap       : (当前价 - MA20) / MA20
        ma60_gap       : (当前价 - MA60) / MA60
        momentum_20    : (当前价 - 20日前价) / 20日前价
        momentum_60    : (当前价 - 60日前价) / 60日前价
        rsi_14         : 14日 RSI（0-100）
        volatility_20  : 20日收益率标准差（年化前）
        volume_ratio_20: 当日成交量 / 20日均量（若无量数据则为 1.0）
    """
    _neutral = {
        "ma20_gap": 0.0,
        "ma60_gap": 0.0,
        "momentum_20": 0.0,
        "momentum_60": 0.0,
        "rsi_14": 50.0,
        "volatility_20": 0.0,
        "volume_ratio_20": 1.0,
    }

    if len(close_prices) < 60:
        return _neutral

    current = close_prices[-1]

    # MA gap
    ma20 = sum(close_prices[-20:]) / 20
    ma60 = sum(close_prices[-60:]) / 60
    ma20_gap = (current - ma20) / ma20 if ma20 != 0 else 0.0
    ma60_gap = (current - ma60) / ma60 if ma60 != 0 else 0.0

    # Momentum
    momentum_20 = (current - close_prices[-21]) / close_prices[-21] if close_prices[-21] != 0 else 0.0
    momentum_60 = (current - close_prices[-61]) / close_prices[-61] if len(close_prices) >= 61 and close_prices[-61] != 0 else 0.0

    # RSI-14
    rsi_14 = _compute_rsi(close_prices, period=14)

    # Volatility-20（20日收益率标准差）
    returns = [
        (close_prices[-i] - close_prices[-i - 1]) / close_prices[-i - 1]
        for i in range(1, 21)
        if close_prices[-i - 1] != 0
    ]
    volatility_20 = _std(returns) if returns else 0.0

    # Volume ratio-20
    volume_ratio_20 = 1.0
    if volumes and len(volumes) >= 21:
        avg_vol = sum(volumes[-21:-1]) / 20
        volume_ratio_20 = volumes[-1] / avg_vol if avg_vol != 0 else 1.0

    return {
        "ma20_gap": round(ma20_gap, 6),
        "ma60_gap": round(ma60_gap, 6),
        "momentum_20": round(momentum_20, 6),
        "momentum_60": round(momentum_60, 6),
        "rsi_14": round(rsi_14, 2),
        "volatility_20": round(volatility_20, 6),
        "volume_ratio_20": round(volume_ratio_20, 4),
    }


def _compute_rsi(prices: List[float], period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(-period, 0):
        diff = prices[i] - prices[i - 1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - 100 / (1 + rs), 2)


def _std(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)
