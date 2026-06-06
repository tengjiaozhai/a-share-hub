from datetime import date


def test_build_performance_returns_empty_when_no_history():
    from src.api.routes_dashboard import _build_performance_payload

    perf = _build_performance_payload(history=[])
    assert perf == {
        "today_return": 0.0,
        "month_return": 0.0,
        "max_drawdown": 0.0,
        "nav_curve": [],
    }


def test_build_performance_computes_returns_and_drawdown():
    from src.api.routes_dashboard import _build_performance_payload

    history = [
        {"trade_date": "2026-05-01", "nav": 1_000_000.0},
        {"trade_date": "2026-05-02", "nav": 1_010_000.0},
        {"trade_date": "2026-05-03", "nav": 1_005_000.0},
        {"trade_date": "2026-06-01", "nav": 1_020_000.0},
        {"trade_date": "2026-06-06", "nav": 1_030_000.0},
    ]
    perf = _build_performance_payload(history=history)
    assert perf["today_return"] == round((1_030_000.0 - 1_020_000.0) / 1_020_000.0, 6)
    assert perf["month_return"] == round((1_030_000.0 - 1_000_000.0) / 1_000_000.0, 6)
    assert perf["max_drawdown"] == round((1_010_000.0 - 1_005_000.0) / 1_010_000.0, 6)
    assert len(perf["nav_curve"]) == 5


def test_build_automation_payload_reports_last_run_and_next():
    from src.api.routes_dashboard import _build_automation_payload

    auto = _build_automation_payload(
        last_run_at="2026-06-06T09:15:00+08:00",
        last_status="success",
        next_run_at="2026-06-09T09:15:00+08:00",
    )
    assert auto["today_status"] == "success"
    assert auto["last_run_at"] == "2026-06-06T09:15:00+08:00"
    assert auto["next_run_at"] == "2026-06-09T09:15:00+08:00"


def test_build_automation_payload_defaults_when_no_run():
    from src.api.routes_dashboard import _build_automation_payload

    auto = _build_automation_payload()
    assert auto["today_status"] == "pending"
    assert auto["last_run_at"] is None
