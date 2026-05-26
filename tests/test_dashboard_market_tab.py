from pathlib import Path


def test_dashboard_contains_market_tab_and_quote_polling():
    content = Path("src/api/dashboard.html").read_text(encoding="utf-8")
    assert "tab-market" in content
    assert "实时行情" in content
    assert "const MARKET_QUOTE_API = '/api/v1/market/quote';" in content
    assert "refreshMarketQuotes" in content
