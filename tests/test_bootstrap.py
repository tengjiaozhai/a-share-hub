from pathlib import Path
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

def test_broker_events_route():
    app = build_app()
    routes = {route.path for route in app.routes}
    assert "/api/v1/broker-events" in routes

def test_kill_switch_status_route():
    app = build_app()
    routes = {route.path for route in app.routes}
    assert "/api/v1/kill-switch/status" in routes
