from fastapi.testclient import TestClient

from src.main import build_app


def _dashboard_html() -> str:
    return TestClient(build_app()).get("/dashboard").text


def test_dashboard_contains_market_tab_and_quote_polling():
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
