from pathlib import Path


def test_dashboard_contains_alpha_operations_tab():
    content = Path("src/api/dashboard.html").read_text(encoding="utf-8")
    assert "view-alpha" in content
    assert "Alpha 代币化证券" in content
    assert "const ALPHA_ASSETS_API = '/api/v1/alpha/assets';" in content
    assert "const ALPHA_TICKETS_API = '/api/v1/alpha/tickets';" in content
    assert "renderAlphaTickets" in content
    assert "submitAlphaTicket" in content


def test_dashboard_contains_alpha_portfolio_and_exceptions_ui():
    content = Path("src/api/dashboard.html").read_text(encoding="utf-8")
    assert "alpha-portfolio-summary" in content
    assert "alpha-positions" in content
    assert "alpha-exceptions" in content
    assert "renderAlphaPortfolio" in content
    assert "renderAlphaExceptions" in content
    assert "Alpha 组合" in content
    assert "Alpha 异常" in content


def test_dashboard_contains_alpha_research_controls():
    content = Path("src/api/dashboard.html").read_text(encoding="utf-8")
    assert "观察列表与候选" in content
    assert "runAlphaScan" in content
    assert "proposeTopAlphaTicket" in content


def test_dashboard_contains_alpha_execution_capability_panel():
    content = Path("src/api/dashboard.html").read_text(encoding="utf-8")
    assert "alpha-execution-capability" in content
    assert "Direct Execution Capability" in content
    assert "const ALPHA_CAPABILITIES_API = '/api/v1/alpha/capabilities';" in content
