from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.core.config import Settings
from src.main import build_app

def test_settings_defaults():
    settings = Settings()
    assert settings.enable_live_trading is False
    assert settings.execution_mode == "shadow"

def test_health_route_available():
    app = build_app()
    routes = {route.path for route in app.routes}
    assert "/health" in routes

def test_execution_plans_ready_route():
    app = build_app()
    routes = {route.path for route in app.routes}
    assert "/api/v1/execution-plans/ready" in routes

def test_decision_runs_route():
    app = build_app()
    routes = {route.path for route in app.routes}
    assert "/api/v1/decision-runs" in routes

def test_portfolio_targets_route():
    app = build_app()
    routes = {route.path for route in app.routes}
    assert "/api/v1/portfolio-targets/active" in routes

def test_reconciliation_status_route():
    app = build_app()
    routes = {route.path for route in app.routes}
    assert "/api/v1/reconciliation/status" in routes

def test_broker_events_route():
    app = build_app()
    routes = {route.path for route in app.routes}
    assert "/api/v1/broker-events" in routes

def test_kill_switch_status_route():
    app = build_app()
    routes = {route.path for route in app.routes}
    assert "/api/v1/kill-switch/status" in routes


def test_app_startup_triggers_fund_etf_spot_prewarm():
    mock_scheduler = type("MockScheduler", (), {"start": lambda self: None, "stop": lambda self: None})()

    with patch("src.main._run_startup_backfill"), \
        patch("src.main._start_fund_startup_prewarm") as mock_prewarm, \
        patch("src.scheduler.daily_scheduler.get_scheduler", return_value=mock_scheduler):
        app = build_app()
        with TestClient(app):
            pass

    mock_prewarm.assert_called_once_with()
