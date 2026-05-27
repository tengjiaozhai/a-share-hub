from src.backtest.engine import run_daily_backtest


def test_run_daily_backtest_produces_equity_curve_and_trades():
    bars = [
        {"date": "2025-01-02", "close": 100.0},
        {"date": "2025-01-03", "close": 102.0},
        {"date": "2025-01-06", "close": 104.0},
    ]

    result = run_daily_backtest(
        symbol="600519.SH",
        bars=bars,
        initial_cash=1_000_000.0,
        signals=[
            {"date": "2025-01-02", "action": "BUY", "target_position_ratio": 0.2},
            {"date": "2025-01-06", "action": "SELL", "target_position_ratio": 0.0},
        ],
    )

    assert len(result["equity_curve"]) == 3
    assert len(result["trades"]) == 2
    assert result["final_nav"] > 0


def test_run_daily_backtest_hold_signal_produces_no_trade():
    bars = [
        {"date": "2025-01-02", "close": 100.0},
        {"date": "2025-01-03", "close": 101.0},
    ]

    result = run_daily_backtest(
        symbol="600519.SH",
        bars=bars,
        initial_cash=500_000.0,
        signals=[
            {"date": "2025-01-02", "action": "HOLD", "target_position_ratio": 0.0},
        ],
    )

    assert len(result["trades"]) == 0
    assert result["final_nav"] == 500_000.0
