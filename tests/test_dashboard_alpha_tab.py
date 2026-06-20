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


def test_dashboard_contains_alpha_operations_tab(_patch_auth):
    html = _dashboard_html()
    assert "view-alpha" in html
    assert "Alpha 持仓助手" in html
    assert "const ALPHA_ASSETS_API = '/api/v1/alpha/assets';" in html
    assert "const ALPHA_TICKETS_API = '/api/v1/alpha/tickets';" in html
    assert "renderAlphaTickets" in html
    assert "submitAlphaTicket" in html


def test_dashboard_contains_alpha_portfolio_and_exceptions_ui(_patch_auth):
    html = _dashboard_html()
    assert "alpha-holdings-summary" in html
    assert "alpha-positions" in html
    assert "alpha-fill-history" in html
    assert "alpha-multi-leg-history" in html
    assert "alpha-exceptions" in html
    assert "renderAlphaPortfolio" in html
    assert "renderAlphaFillHistory" in html
    assert "renderAlphaMultiLegHistory" in html
    assert "renderAlphaExceptions" in html
    assert "当前持仓" in html
    assert "Alpha 异常" in html


def test_dashboard_contains_alpha_research_controls(_patch_auth):
    html = _dashboard_html()
    assert "观察列表与持仓候选" in html
    assert "runAlphaScan" in html
    assert "proposeTopAlphaTicket" in html


def test_dashboard_contains_alpha_execution_capability_panel(_patch_auth):
    html = _dashboard_html()
    assert "alpha-execution-capability" in html
    assert "Direct Execution Capability" in html
    assert "const ALPHA_CAPABILITIES_API = '/api/v1/alpha/capabilities';" in html


def test_dashboard_contains_alpha_manual_fill_entry_ui(_patch_auth):
    html = _dashboard_html()
    assert 'id="alpha-fill-form"' in html
    assert 'id="alpha-fill-ticket"' in html
    assert 'id="alpha-fill-operator"' in html
    assert 'id="alpha-fill-qty"' in html
    assert 'id="alpha-fill-price"' in html
    assert 'id="alpha-fill-executed-at"' in html
    assert 'id="alpha-rebuild-opening-cash"' in html
    assert 'id="alpha-rebuild-price-map"' in html
    assert "submitAlphaManualFill" in html
