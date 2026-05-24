from pathlib import Path


def test_missing_features_analysis_tracks_review_findings():
    text = Path("docs/missing-features-analysis.md").read_text(encoding="utf-8")
    assert "实现深度分级" in text
    assert "execution_order" in text
    assert "kill_switch_event" in text
    assert "`pull_execution_plans.py` | ❌ 缺失" in text
    assert "`decide`" in text
