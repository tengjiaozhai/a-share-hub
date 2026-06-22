from src.alpha.analysis_risk import evaluate_risk
from src.alpha.analysis_models import AnalysisSnapshot, ResearchPlan, TraderProposal


def _snapshot() -> AnalysisSnapshot:
    return AnalysisSnapshot(
        symbol="600703.SH",
        market="a",
        currency="CNY",
        as_of="2026-06-22",
        quantity=300,
        weighted_avg_cost=13.333333,
        close=16.0,
        market_value=4800.0,
        unrealized_pnl=800.0,
        unrealized_pnl_ratio=0.06,
        position_ratio=0.08,
        stop_loss_ratio=-0.08,
        take_profit_ratio=0.20,
        technical={
            "ma20": 15.7,
            "ma60": 14.8,
            "ma20_gap": 0.02,
            "ma60_gap": 0.08,
            "volume_ratio_20": 1.2,
            "bar_count": 61,
            "reclaimed_ma20": True,
        },
        fundamentals={"status": "ok", "pe_ratio": 18.2},
        news={"status": "unavailable", "items": []},
        data_quality={"status": "partial", "missing": ["news"]},
    )


def _research() -> ResearchPlan:
    return ResearchPlan(
        rating="OVERWEIGHT",
        thesis="上涨趋势保持",
        technical_view="回踩 MA20 后重新站稳",
        fundamental_view="估值数据有限",
        sentiment_view="新闻不可用",
        catalysts=["成交量确认"],
        risks=["新闻缺失"],
        confidence=0.66,
        data_gaps=["news"],
    )


def _proposal() -> TraderProposal:
    return TraderProposal(
        action="BUY",
        reasoning="研究方向偏多且位置未追高",
        entry_low=15.8,
        entry_high=16.2,
        stop_loss=15.0,
        take_profit=19.0,
        position_ratio=0.1,
    )


def test_stop_loss_forces_exit():
    snapshot, bullish_research, buy_proposal = _snapshot(), _research(), _proposal()
    breached = snapshot.model_copy(update={"unrealized_pnl_ratio": -0.09})
    decision = evaluate_risk(breached, bullish_research, buy_proposal, max_position_ratio=0.2)
    assert decision.action == "EXIT"
    assert decision.triggered_rules == ["stop_loss_breached"]


def test_take_profit_reduces_before_llm_buy():
    snapshot, bullish_research, buy_proposal = _snapshot(), _research(), _proposal()
    profitable = snapshot.model_copy(update={"unrealized_pnl_ratio": 0.22})
    decision = evaluate_risk(profitable, bullish_research, buy_proposal, max_position_ratio=0.2)
    assert decision.action == "REDUCE"


def test_add_requires_trend_pullback_and_capacity():
    snapshot, bullish_research, buy_proposal = _snapshot(), _research(), _proposal()
    eligible = snapshot.model_copy(update={
        "position_ratio": 0.08,
        "technical": {
            "ma20": 15.7,
            "ma60": 14.8,
            "ma20_gap": 0.02,
            "ma60_gap": 0.08,
            "volume_ratio_20": 1.2,
            "bar_count": 61,
            "reclaimed_ma20": True,
        },
    })
    decision = evaluate_risk(eligible, bullish_research, buy_proposal, max_position_ratio=0.2)
    assert decision.action == "ADD"


def test_missing_technical_history_blocks_add():
    snapshot, bullish_research, buy_proposal = _snapshot(), _research(), _proposal()
    partial = snapshot.model_copy(update={
        "data_quality": {"status": "partial", "missing": ["technical_history", "news"]},
    })
    decision = evaluate_risk(partial, bullish_research, buy_proposal, max_position_ratio=0.2)
    assert decision.action == "HOLD"
