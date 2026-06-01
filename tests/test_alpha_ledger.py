from src.alpha.ledger import AlphaPortfolioState, AlphaPositionState, apply_manual_fill, mark_to_market


def test_apply_manual_fill_updates_cash_positions_and_realized_pnl():
    state = AlphaPortfolioState(
        cash_balance=10_000.0,
        realized_pnl=0.0,
        positions={"AAPLx": AlphaPositionState(symbol="AAPLx", quantity=1.0, avg_cost=200.0)},
    )

    next_state = apply_manual_fill(state, symbol="AAPLx", side="SELL", quantity=0.4, price=220.0)
    summary = mark_to_market(next_state, {"AAPLx": 225.0})

    assert round(next_state.cash_balance, 2) == 10_088.0
    assert round(next_state.realized_pnl, 2) == 8.0
    assert round(next_state.positions["AAPLx"].quantity, 2) == 0.6
    assert round(summary["unrealized_pnl"], 2) == 15.0
    assert round(summary["nav"], 2) == 10_223.0