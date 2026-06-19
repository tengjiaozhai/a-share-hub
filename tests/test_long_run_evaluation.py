from datetime import datetime, timedelta

from src.evaluation.long_run import run_long_horizon_evaluation


class FakeStore:
    def list_decision_runs(self, user_id, limit=None):
        return [{"decision_run_id": f"dr-{i}"} for i in range(5)]

    def list_account_snapshots(self, user_id, since=None):
        base = datetime(2026, 6, 1)
        return [
            {"created_at": (base + timedelta(days=0)).isoformat(), "nav": 1_000_000.0},
            {"created_at": (base + timedelta(days=1)).isoformat(), "nav": 1_020_000.0},
            {"created_at": (base + timedelta(days=2)).isoformat(), "nav": 1_010_000.0},
        ]

    def list_execution_orders(self, user_id, limit=None):
        return [
            {"execution_order_id": "eo-1", "status": "FILLED"},
            {"execution_order_id": "eo-2", "status": "READY"},
        ]

    def list_broker_events(self, limit=None):
        return [
            {"event_type": "FILLED", "payload": {"pnl_delta": 1000.0}},
            {"event_type": "SUBMITTED", "payload": {}},
        ]

    def get_reconciliation_status(self, user_id):
        return {"open_orders": 1, "broker_event_count": 2, "healthy": True}


def test_run_long_horizon_evaluation_computes_metrics_from_snapshots():
    result = run_long_horizon_evaluation(store=FakeStore(), window="1m", mode="shadow")

    assert result["window"] == "1m"
    assert result["metrics"]["total_return"] == 0.01
    assert result["metrics"]["max_drawdown"] < 0
    assert result["metrics"]["decision_count"] == 5
    assert result["metrics"]["fill_rate"] == 0.5
    assert result["metrics"]["unreconciled_order_count"] == 1


def test_run_long_horizon_evaluation_rejects_unknown_window():
    result = run_long_horizon_evaluation(store=FakeStore(), window="2w", mode="shadow")

    assert result["status"] == "error"
    assert result["reason"] == "unsupported window"
