import pytest
from pydantic import ValidationError

from src.alpha.analysis_models import ResearchPlan, RiskDecision, TraderProposal


def test_research_plan_accepts_only_five_ratings():
    plan = ResearchPlan(
        rating="OVERWEIGHT",
        thesis="趋势保持，但估值证据有限",
        technical_view="收盘价位于 MA20 与 MA60 上方",
        fundamental_view="仅有 PE 数据",
        sentiment_view="新闻数据不可用",
        catalysts=["成交量确认"],
        risks=["新闻数据缺失"],
        confidence=0.68,
        data_gaps=["news"],
    )
    assert plan.rating == "OVERWEIGHT"

    with pytest.raises(ValidationError):
        ResearchPlan(
            rating="STRONG_BUY",
            thesis="invalid",
            technical_view="invalid",
            fundamental_view="invalid",
            sentiment_view="invalid",
            catalysts=[],
            risks=[],
            confidence=0.5,
            data_gaps=[],
        )


def test_trader_and_risk_actions_have_distinct_contracts():
    proposal = TraderProposal(
        action="BUY",
        reasoning="趋势回踩后重新确认",
        entry_low=16.0,
        entry_high=16.8,
        stop_loss=15.0,
        take_profit=19.0,
        position_ratio=0.1,
    )
    decision = RiskDecision(
        action="ADD",
        reason="研究和交易方向一致，且未触发硬限制",
        triggered_rules=["trend_pullback_confirmed"],
        approved_position_ratio=0.1,
    )
    assert proposal.action == "BUY"
    assert decision.action == "ADD"
