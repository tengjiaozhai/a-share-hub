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


def test_dashboard_run_contract_mentions_stream_endpoints_and_event_types():
    text = Path("docs/dashboard-run-contract.md").read_text(encoding="utf-8")
    assert "/api/v1/dashboard/runs" in text
    assert "/api/v1/dashboard/runs/{run_context_id}/events" in text
    assert "run.accepted" in text
    assert "stage.updated" in text
    assert "run.completed" in text
    assert "run_pnl_summary" in text
    assert "reconcile_items" in text
