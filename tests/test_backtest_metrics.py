from src.backtest.metrics import calculate_metrics


def test_calculate_metrics_returns_drawdown_and_turnover():
    metrics = calculate_metrics(
        equity_curve=[1.0, 1.02, 0.99, 1.05],
        trades=[{"side": "BUY", "notional": 100000}, {"side": "SELL", "notional": 100000}],
    )

    assert set(metrics) >= {"total_return", "max_drawdown", "turnover", "win_rate"}


def test_total_return_calculation():
    metrics = calculate_metrics(
        equity_curve=[1_000_000.0, 1_100_000.0],
        trades=[],
    )

    assert abs(metrics["total_return"] - 0.10) < 1e-9
    assert metrics["max_drawdown"] == 0.0
