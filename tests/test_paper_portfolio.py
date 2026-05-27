from src.execution.paper_portfolio import apply_fill, compute_nav


def test_apply_fill_updates_cash_position_and_average_cost():
    state = {"cash": 1_000_000.0, "positions": {}}

    new_state = apply_fill(
        state=state,
        symbol="600519.SH",
        side="BUY",
        quantity=100,
        price=1200.0,
    )

    assert new_state["cash"] == 880000.0
    assert new_state["positions"]["600519.SH"]["quantity"] == 100
    assert new_state["positions"]["600519.SH"]["avg_cost"] == 1200.0


def test_apply_fill_sell_reduces_position():
    state = {
        "cash": 880_000.0,
        "positions": {"600519.SH": {"quantity": 100, "avg_cost": 1200.0}},
    }

    new_state = apply_fill(
        state=state,
        symbol="600519.SH",
        side="SELL",
        quantity=50,
        price=1300.0,
    )

    assert new_state["cash"] == 880_000.0+ 50 * 1300.0
    assert new_state["positions"]["600519.SH"]["quantity"] == 50


def test_compute_nav_sums_cash_and_mark_to_market():
    state = {
        "cash": 500_000.0,
        "positions": {
            "600519.SH": {"quantity": 100, "avg_cost": 1200.0},
        },
    }
    prices = {"600519.SH": 1300.0}

    nav = compute_nav(state, prices)

    assert nav == 500_000.0 + 100 * 1300.0
