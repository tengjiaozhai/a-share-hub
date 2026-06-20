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


def test_dashboard_contains_holdings_analysis_tab(_patch_auth):
    html = _dashboard_html()
    assert "view-alpha" in html
    assert "持仓分析" in html
    assert "const ALPHA_ASSETS_API = '/api/v1/alpha/assets';" in html
    assert "const ALPHA_REPORT_API = '/api/v1/alpha/portfolio/report';" in html
    assert "loadAlphaReport" in html


def test_dashboard_contains_holdings_and_history_ui(_patch_auth):
    html = _dashboard_html()
    assert "alpha-holdings-summary" in html
    assert "alpha-positions" in html
    assert "alpha-fill-history" in html
    assert "alpha-multi-leg-history" in html
    assert "renderAlphaPortfolio" in html
    assert "renderAlphaFillHistory" in html
    assert "renderAlphaMultiLegHistory" in html
    assert "当前持仓" in html
    assert "成交 / Multi-leg 历史" in html


def test_dashboard_contains_code_analysis_first_controls(_patch_auth):
    html = _dashboard_html()
    assert 'id="alpha-report-symbol"' in html
    assert 'id="alpha-report-position-ratio"' in html
    assert 'id="alpha-report-buy-time"' in html
    assert 'id="alpha-report-generate"' in html
    assert "股票代码" in html
    assert "持仓仓位 (%)" in html
    assert "买入时间" in html
    assert "分析股票" in html


def test_dashboard_removes_legacy_alpha_ops_sections(_patch_auth):
    html = _dashboard_html()
    assert "alpha-execution-capability" not in html
    assert "Direct Execution Capability" not in html
    assert "Alpha 异常" not in html
    assert "建议单队列" not in html
    assert "建议单录入" not in html
    assert "观察列表与持仓候选" not in html


def test_dashboard_removes_alpha_manual_fill_entry_ui(_patch_auth):
    html = _dashboard_html()
    assert 'id="alpha-fill-form"' not in html
    assert 'id="alpha-fill-ticket"' not in html
    assert 'id="alpha-fill-operator"' not in html
    assert 'id="alpha-fill-qty"' not in html
    assert 'id="alpha-fill-price"' not in html
    assert 'id="alpha-fill-executed-at"' not in html
    assert 'id="alpha-rebuild-opening-cash"' not in html
    assert 'id="alpha-rebuild-price-map"' not in html
    assert "submitAlphaManualFill" not in html
    assert "手动回填成交" not in html
