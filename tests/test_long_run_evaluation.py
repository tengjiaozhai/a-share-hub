import pytest
from src.evaluation.long_run import run_long_horizon_evaluation


class FakeStore:
    def list_decision_runs(self, limit=None):
        return [{"decision_run_id": f"dr-{i}"} for i in range(5)]

    def get_reconciliation_status(self):
        return {"open_orders": 0, "broker_event_count": 8, "healthy": True}


def test_run_long_horizon_evaluation_supports_1m_window():
    result = run_long_horizon_evaluation(store=FakeStore(), window="1m", mode="shadow")

    assert result["window"] == "1m"
    assert set(result["metrics"]) >= {
        "total_return",
        "max_drawdown",
        "turnover",
        "decision_count",
        "fill_rate",
        "unreconciled_order_count",
    }


def test_run_long_horizon_evaluation_supports_3m_window():
    result = run_long_horizon_evaluation(store=FakeStore(), window="3m", mode="shadow")
    assert result["window"] == "3m"
    assert result["metrics"]["decision_count"] == 5


def test_run_long_horizon_evaluation_supports_1y_window():
    result = run_long_horizon_evaluation(store=FakeStore(), window="1y", mode="shadow")
    assert result["window"] == "1y"
