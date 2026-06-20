import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from src.api import auth_security as _auth_security
from src.api.auth_security import create_auth_token
from src.api.dependencies import get_current_user, get_current_user_id, get_user_runtime_store
from src.core.config import Settings
from src.core.tenant import TenantContext
from src.main import build_app
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


@pytest.fixture
def _patch_auth(monkeypatch):
    monkeypatch.setattr(
        _auth_security,
        "get_current_user_from_request",
        lambda request: {
            "user_id": "test-user",
            "username": "test",
            "email": "test@example.com",
            "role": "user",
        },
    )


def _dashboard_html() -> str:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine, TenantContext("test-user"))
    app = build_app()
    app.dependency_overrides[get_user_runtime_store] = lambda: store
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "test-user",
        "username": "test",
        "email": "test@example.com",
        "role": "user",
    }
    app.dependency_overrides[get_current_user_id] = lambda: "test-user"
    settings = Settings()
    token = create_auth_token("test-user", settings)
    client = TestClient(app)
    client.cookies.set(settings.auth_cookie_name, token)
    return client.get("/dashboard").text


def test_dashboard_contains_market_tab_and_quote_polling(_patch_auth):
    html = _dashboard_html()
    assert "view-market" in html
    assert "A 股工作台" in html
    assert "aLoadQuotes" in html
    assert "a-quotes-table" in html


def test_dashboard_contains_market_scan_controls():
    from src.api.dashboard_page.render import render_dashboard_html

    html = render_dashboard_html()

    assert 'id="scan-btn"' in html
    assert "/api/v1/dashboard/scan" in html
    assert "/api/v1/dashboard/scan-us" in html
