from fastapi.testclient import TestClient

from src.main import build_app


def _dashboard_html() -> str:
    return TestClient(build_app()).get("/dashboard").text


def test_dashboard_contains_alpha_operations_tab():
    html = _dashboard_html()
    assert "view-alpha" in html
    assert "Alpha 持仓助手" in html
    assert "const ALPHA_ASSETS_API = '/api/v1/alpha/assets';" in html
    assert "const ALPHA_TICKETS_API = '/api/v1/alpha/tickets';" in html
    assert "renderAlphaTickets" in html
    assert "submitAlphaTicket" in html


def test_dashboard_contains_alpha_portfolio_and_exceptions_ui():
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


def test_dashboard_contains_alpha_research_controls():
    html = _dashboard_html()
    assert "观察列表与持仓候选" in html
    assert "runAlphaScan" in html
    assert "proposeTopAlphaTicket" in html


def test_dashboard_contains_alpha_execution_capability_panel():
    html = _dashboard_html()
    assert "alpha-execution-capability" in html
    assert "Direct Execution Capability" in html
    assert "const ALPHA_CAPABILITIES_API = '/api/v1/alpha/capabilities';" in html


def test_dashboard_contains_alpha_manual_fill_entry_ui():
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
