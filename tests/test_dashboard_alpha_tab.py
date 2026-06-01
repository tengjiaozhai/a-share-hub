from pathlib import Path


def test_dashboard_contains_alpha_operations_tab():
    content = Path("src/api/dashboard.html").read_text(encoding="utf-8")
    assert "view-alpha" in content
    assert "Alpha 代币化证券" in content
    assert "const ALPHA_ASSETS_API = '/api/v1/alpha/assets';" in content
    assert "const ALPHA_TICKETS_API = '/api/v1/alpha/tickets';" in content
    assert "renderAlphaTickets" in content
    assert "submitAlphaTicket" in content
