import pytest
from pydantic import ValidationError

from src.alpha.analysis_run_models import (
    AnalysisRunCreateRequest,
    AnalysisRunCreatedResponse,
    AnalysisStageUpdate,
    AnalysisRunSummary,
    AnalysisRunDetail,
)


def test_create_request_rejects_empty_symbol():
    with pytest.raises(ValidationError):
        AnalysisRunCreateRequest(symbol="", backtest_window="60d", include_backtest=True)


def test_create_request_accepts_valid_symbol():
    req = AnalysisRunCreateRequest(symbol="MU.US", backtest_window="60d", include_backtest=True)
    assert req.symbol == "MU.US"
    assert req.backtest_window == "60d"
    assert req.include_backtest is True


def test_stage_update_cumulative_payload():
    payload = AnalysisStageUpdate(
        run_id="alpha-ar-1",
        symbol="MU.US",
        market="us",
        stage="research",
        status="done",
        message="研究结论已生成",
        snapshot={"close": 16.0},
        research={"rating": "OVERWEIGHT"},
        trader=None,
        risk=None,
        backtest=None,
        seq=2,
    )
    assert payload.stage == "research"
    assert payload.snapshot["close"] == 16.0
    assert payload.seq == 2


def test_summary_keys_are_stable():
    summary = AnalysisRunSummary(
        run_id="alpha-ar-1",
        symbol="MU.US",
        market="us",
        status="completed",
        current_stage="completed",
        risk_action="ADD",
        research_rating="OVERWEIGHT",
        research_confidence=0.7,
        close_date="2026-06-22",
        created_at="2026-06-22T15:10:00+08:00",
    )
    assert summary.market == "us"
    assert summary.risk_action == "ADD"


def test_detail_has_all_sections():
    detail = AnalysisRunDetail(
        run_id="alpha-ar-1",
        symbol="MU.US",
        market="us",
        status="completed",
        current_stage="completed",
        model_name="deepseek-v4-pro",
        created_at="2026-06-22T15:10:00+08:00",
        started_at="2026-06-22T15:10:00+08:00",
        finished_at="2026-06-22T15:11:00+08:00",
        snapshot={"close": 16.0},
        research={"rating": "OVERWEIGHT"},
        trader={"action": "BUY"},
        risk={"action": "ADD"},
        backtest={"status": "ok", "total_return": 0.05},
        error=None,
        error_stage=None,
    )
    assert detail.snapshot["close"] == 16.0
    assert detail.risk["action"] == "ADD"


def test_response_has_stream_url():
    response = AnalysisRunCreatedResponse(
        run_id="alpha-ar-1",
        symbol="MU.US",
        market="us",
        status="accepted",
        stream_url="/api/v1/alpha/analysis-runs/alpha-ar-1/events",
        created_at="2026-06-22T15:10:00+08:00",
    )
    assert "/events" in response.stream_url