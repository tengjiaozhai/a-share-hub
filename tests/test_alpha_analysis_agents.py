from src.alpha.analysis_agents import ResearchManager, Trader
from src.alpha.analysis_models import AnalysisSnapshot


class FakeStructuredLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


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
        unrealized_pnl_ratio=0.2,
        position_ratio=0.08,
        stop_loss_ratio=-0.08,
        take_profit_ratio=0.20,
        technical={"ma20": 15.7, "ma60": 14.8, "reclaimed_ma20": True},
        fundamentals={"status": "ok", "pe_ratio": 18.2},
        news={"status": "unavailable", "items": []},
        data_quality={"status": "partial", "missing": ["news"]},
    )


def test_trader_receives_research_plan_and_snapshot():
    snapshot = _snapshot()
    llm = FakeStructuredLLM([
        {
            "rating": "OVERWEIGHT",
            "thesis": "趋势保持",
            "technical_view": "MA20 高于 MA60",
            "fundamental_view": "估值数据有限",
            "sentiment_view": "新闻不可用",
            "catalysts": ["回踩确认"],
            "risks": ["新闻缺失"],
            "confidence": 0.66,
            "data_gaps": ["news"],
        },
        {
            "action": "BUY",
            "reasoning": "研究方向偏多且位置未追高",
            "entry_low": 15.8,
            "entry_high": 16.2,
            "stop_loss": 15.0,
            "take_profit": 19.0,
            "position_ratio": 0.1,
        },
    ])
    research = ResearchManager(llm).analyze(snapshot)
    proposal = Trader(llm).propose(snapshot, research)

    assert proposal.action == "BUY"
    assert '"rating": "OVERWEIGHT"' in llm.calls[1]["user_prompt"]
    assert '"weighted_avg_cost"' in llm.calls[1]["user_prompt"]


def test_research_manager_normalizes_partial_llm_payload():
    snapshot = _snapshot()
    llm = FakeStructuredLLM([
        {
            "rating": "HOLD",
            "confidence": 0.55,
            "data_gaps": ["news"],
        },
    ])

    research = ResearchManager(llm).analyze(snapshot)

    assert research.rating == "HOLD"
    assert research.thesis
    assert research.technical_view
    assert research.fundamental_view
    assert research.sentiment_view
    assert research.risks == ["news"]
