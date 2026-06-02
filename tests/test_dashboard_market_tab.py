from fastapi.testclient import TestClient

from src.main import build_app


def _dashboard_html() -> str:
    return TestClient(build_app()).get("/dashboard").text


def test_dashboard_contains_market_tab_and_quote_polling():
    html = _dashboard_html()
    assert "view-market" in html
    assert "实时行情" in html
    assert "const MARKET_QUOTE_API = '/api/v1/market/quote';" in html
    assert "refreshMarketQuotes" in html
    assert "tb-market-full" in html
