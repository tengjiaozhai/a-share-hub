from typing import Dict, Any

def build_decision_input_snapshot(
    symbol: str,
    features: Dict[str, Any],
    market_context: Dict[str, Any],
) -> Dict[str, Any]:
    """构建决策输入快照"""
    return {
        "symbol": symbol,
        "features": features,
        "market_context": market_context,
    }
