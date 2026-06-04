from src.execution.paper_portfolio import apply_fill, compute_nav


def test_apply_buy_fill_updates_cash_position_and_avg_cost():
    state = {"cash": 1_000_000.0, "positions": {}}

    result = apply_fill(
        state=state,
        symbol="600519.SH",
        side="BUY",
        quantity=100,
        price=100.0,
        fee=5.0,
        trade_date="2026-06-04",
    )

    assert result["cash"] == 989_995.0
    assert result["positions"]["600519.SH"]["quantity"] == 100
    assert result["positions"]["600519.SH"]["avg_cost"] == 100.0
    assert result["realized_pnl"] == 0.0


def test_apply_sell_fill_realizes_pnl_and_blocks_oversell():
    state = {
        "cash": 900_000.0,
        "positions": {"600519.SH": {"quantity": 100, "avg_cost": 100.0, "buy_date": "2026-06-03"}},
    }

    result = apply_fill(
        state=state,
        symbol="600519.SH",
        side="SELL",
        quantity=100,
        price=110.0,
        fee=5.0,
        trade_date="2026-06-04",
    )

    assert result["cash"] == 910_995.0
    assert result["positions"]["600519.SH"]["quantity"] == 0
    assert result["realized_pnl"] == 995.0


def test_compute_nav_marks_positions_to_market():
    state = {
        "cash": 900_000.0,
        "positions": {"600519.SH": {"quantity": 100, "avg_cost": 100.0}},
    }

    assert compute_nav(state, {"600519.SH": 110.0}) == 911_000.0
