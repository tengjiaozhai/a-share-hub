from typing import List, Dict, Any

def compute_feature_row(close_prices: List[float]) -> Dict[str, float]:
    """计算技术特征"""
    if len(close_prices) < 20:
        return {"ma20_gap": 0.0, "rsi": 50.0}
    
    current = close_prices[-1]
    ma20 = sum(close_prices[-20:]) / 20
    
    # 简单RSI计算
    gains = []
    losses = []
    for i in range(1, min(15, len(close_prices))):
        diff = close_prices[-i] - close_prices[-i-1]
        if diff > 0:
            gains.append(diff)
        else:
            losses.append(abs(diff))
    
    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0.0001
    rsi = 100 - (100 / (1 + avg_gain / avg_loss))
    
    return {
        "ma20_gap": (current - ma20) / ma20,
        "rsi": rsi
    }