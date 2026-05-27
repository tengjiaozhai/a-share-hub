from pathlib import Path


def test_missing_features_analysis_tracks_review_findings():
    text = Path("docs/missing-features-analysis.md").read_text(encoding="utf-8")
    assert "实现深度分级" in text
    assert "execution_order" in text
    assert "kill_switch_event" in text
    assert "`pull_execution_plans.py` | ❌ 缺失" in text
    assert "`decide`" in text


def test_dashboard_runbook_mentions_market_endpoints():
    content = Path("docs/runbooks/dashboard_user_guide.md").read_text(encoding="utf-8")
    assert "/api/v1/market/stocks" in content
    assert "/api/v1/market/quote" in content
    assert "000858.SZ" in content
    assert "quote symbol not found" in content
