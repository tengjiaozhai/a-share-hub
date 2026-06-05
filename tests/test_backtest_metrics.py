from src.backtest.metrics import calculate_metrics


def test_calculate_metrics_pairs_trades_for_win_rate():
    metrics = calculate_metrics(
        equity_curve=[1_000_000.0, 1_010_000.0, 1_020_000.0],
        trades=[
            {"side": "BUY", "quantity": 100, "price": 100.0, "notional": 10_000.0},
            {"side": "SELL", "quantity": 100, "price": 110.0, "notional": 11_000.0},
        ],
    )

    assert metrics["total_return"] == 0.02
    assert metrics["max_drawdown"] == 0.0
    assert metrics["turnover"] == 0.021
    assert metrics["win_rate"] == 1.0


def test_calculate_metrics_handles_losing_pair():
    metrics = calculate_metrics(
        equity_curve=[1_000_000.0, 990_000.0],
        trades=[
            {"side": "BUY", "quantity": 100, "price": 100.0, "notional": 10_000.0},
            {"side": "SELL", "quantity": 100, "price": 90.0, "notional": 9_000.0},
        ],
    )

    assert metrics["win_rate"] == 0.0
    assert metrics["max_drawdown"] == -0.01
