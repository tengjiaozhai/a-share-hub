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
