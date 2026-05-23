from typing import Dict, Any

def build_target_position(
    symbol: str,
    action: str,
    target_position_ratio: float,
    net_asset_value: float,
) -> Dict[str, Any]:
    """构建目标仓位"""
    target_value = int(net_asset_value * target_position_ratio)
    return {
        "symbol": symbol,
        "action": action,
        "target_value": target_value,
        "target_position_ratio": target_position_ratio,
    }
