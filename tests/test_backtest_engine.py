from src.backtest.engine import run_daily_backtest


def test_run_daily_backtest_buys_lots_once_and_applies_costs():
    bars = [
        {"date": f"2026-01-{i + 1:02d}", "open": 100.0, "close": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i, "volume": 1_000}
        for i in range(5)
    ]

    result = run_daily_backtest(
        symbol="600519.SH",
        bars=bars,
        initial_cash=1_000_000.0,
        signals=[
            {"date": "2026-01-01", "action": "BUY", "target_position_ratio": 0.2},
            {"date": "2026-01-02", "action": "BUY", "target_position_ratio": 0.2},
            {"date": "2026-01-05", "action": "SELL", "target_position_ratio": 0.0},
        ],
        lot_size=100,
        fee_bps=3.0,
        slippage_bps=5.0,
    )

    assert len(result["trades"]) == 2
    assert result["trades"][0]["quantity"] % 100 == 0
    assert result["trades"][0]["fee"] > 0
    assert result["trades"][0]["side"] == "BUY"
    assert result["trades"][1]["side"] == "SELL"
    assert result["final_nav"] > 0


def test_run_daily_backtest_hold_signal_produces_no_trade():
    result = run_daily_backtest(
        symbol="600519.SH",
        bars=[
            {"date": "2026-01-01", "close": 100.0, "volume": 1_000},
            {"date": "2026-01-02", "close": 101.0, "volume": 1_000},
        ],
        initial_cash=500_000.0,
        signals=[{"date": "2026-01-01", "action": "HOLD", "target_position_ratio": 0.0}],
        lot_size=100,
        fee_bps=3.0,
        slippage_bps=5.0,
    )

    assert result["trades"] == []
    assert result["final_nav"] == 500_000.0
