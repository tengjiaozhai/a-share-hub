from src.portfolio.target_planner import build_target_position, build_target_positions


def test_build_target_position_uses_watchlist_allocation_and_lot_size():
    target = build_target_position(
        symbol="600519.SH",
        action="BUY",
        capital_base=1_000_000,
        max_position_ratio=0.2,
        watchlist_size=4,
        price=103.0,
        lot_size=100,
    )

    assert target["target_value"] == 50_000
    assert target["target_position_ratio"] == 0.05
    assert target["quantity"] == 400
    assert target["notional"] == 41_200


def test_build_target_position_sell_uses_current_position_quantity():
    target = build_target_position(
        symbol="600519.SH",
        action="SELL",
        capital_base=1_000_000,
        max_position_ratio=0.2,
        watchlist_size=4,
        price=103.0,
        lot_size=100,
        current_quantity=350,
    )

    assert target["target_value"] == 0
    assert target["quantity"] == 350
    assert target["target_position_ratio"] == 0.0


def test_build_target_positions_ignores_hold_actions():
    targets = build_target_positions(
        decisions=[
            {"symbol": "600519.SH", "action": "BUY"},
            {"symbol": "000001.SZ", "action": "HOLD"},
        ],
        prices={"600519.SH": 100.0, "000001.SZ": 10.0},
        capital_base=1_000_000,
        max_position_ratio=0.2,
        lot_size=100,
        current_positions={},
    )

    assert len(targets) == 1
    assert targets[0]["symbol"] == "600519.SH"


def test_build_target_position_uses_single_share_lots_for_us_symbols():
    target = build_target_position(
        symbol="AAPL",
        action="BUY",
        capital_base=10_000,
        max_position_ratio=0.2,
        watchlist_size=5,
        price=150.0,
        lot_size_a=100,
        lot_size_us=1,
    )

    assert target["target_value"] == 400
    assert target["quantity"] == 2
    assert target["notional"] == 300
    assert target["lot_size"] == 1


def test_build_target_positions_keeps_zero_quantity_buy_with_diagnostics():
    targets = build_target_positions(
        decisions=[{"symbol": "600519.SH", "action": "BUY"}],
        prices={"600519.SH": 2000.0},
        capital_base=10_000,
        max_position_ratio=0.2,
        lot_size_a=100,
        current_positions={},
    )

    assert len(targets) == 1
    assert targets[0]["quantity"] == 0
    assert targets[0]["lot_size"] == 100
    assert targets[0]["raw_quantity"] == 1.0
    assert targets[0]["rounding_loss_quantity"] == 1.0
