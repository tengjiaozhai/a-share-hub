import pytest
from pathlib import Path


def test_missing_features_analysis_tracks_review_findings():
    text = Path("docs/missing-features-analysis.md").read_text(encoding="utf-8")
    assert "实现深度分级" in text
    assert "execution_order" in text
    assert "kill_switch_event" in text
    assert "`pull_execution_plans.py` | ❌ 缺失" in text
    assert "`decide`" in text


def test_dashboard_runbook_mentions_market_quote_and_stock_list_endpoints():
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


@pytest.mark.xfail(reason="docs/sop.md needs to be updated to mention run_context_id")
def test_sop_mentions_run_trace_and_reconcile_fields():
    text = Path("docs/sop.md").read_text(encoding="utf-8")
    assert "run_context_id" in text
    assert "成本价" in text
    assert "现价" in text
    assert "未实现盈亏" in text


def test_local_aws_sync_guide_mentions_stream_release_order():
    text = Path("docs/local-aws-sync-guide.md").read_text(encoding="utf-8")
    assert "alembic upgrade head" in text
    assert "先部署后端，再部署前端，并在同一发布窗口切换到 `/api/v1/dashboard/runs`" in text
    assert "scripts/run_dashboard_stream_smoke.sh" in text
