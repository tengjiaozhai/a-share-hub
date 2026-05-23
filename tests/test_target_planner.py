from src.portfolio.target_planner import build_target_position

def test_buy_decision_creates_target_value_from_ratio():
    target = build_target_position(
        symbol="600519.SH",
        action="BUY",
        target_position_ratio=0.1,
        net_asset_value=1_000_000,
    )
    assert target["target_value"] == 100000
    assert target["action"] == "BUY"

def test_sell_decision_creates_target_value():
    target = build_target_position(
        symbol="300750.SZ",
        action="SELL",
        target_position_ratio=0.05,
        net_asset_value=500_000,
    )
    assert target["target_value"] == 25000
