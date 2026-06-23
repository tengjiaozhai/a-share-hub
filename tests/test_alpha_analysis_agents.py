from src.alpha.analysis_agents import ResearchManager, Trader
from src.alpha.analysis_models import AnalysisSnapshot
from src.agents.llm_client import LLMGenerationError


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


def test_research_manager_normalizes_text_confidence():
    snapshot = _snapshot()
    llm = FakeStructuredLLM([
        {
            "rating": "HOLD",
            "confidence": "low",
            "data_gaps": ["news"],
        },
    ])

    research = ResearchManager(llm).analyze(snapshot)

    assert research.confidence == 0.4


def test_trader_normalizes_text_price_fields():
    snapshot = _snapshot()
    research = ResearchManager(FakeStructuredLLM([{"rating": "HOLD"}])).analyze(snapshot)
    llm = FakeStructuredLLM([
        {
            "action": "HOLD",
            "reasoning": "等待",
            "entry_low": "low",
            "entry_high": "high",
            "stop_loss": "stop",
            "take_profit": "take",
            "position_ratio": "10%",
        },
    ])

    proposal = Trader(llm).propose(snapshot, research)

    assert proposal.entry_low == snapshot.close
    assert proposal.entry_high == snapshot.close
    assert proposal.position_ratio == 0.0


def test_research_manager_falls_back_when_llm_output_is_unusable():
    snapshot = _snapshot()

    class BrokenLLM:
        def generate_json(self, **kwargs):
            raise LLMGenerationError("DeepSeek returned invalid JSON")

    research = ResearchManager(BrokenLLM()).analyze(snapshot)

    assert research.rating == "HOLD"
    assert research.confidence == 0.2
    assert "LLM 输出不可用" in research.data_gaps[0]


def test_trader_falls_back_when_llm_output_is_unusable():
    snapshot = _snapshot()
    research = ResearchManager(FakeStructuredLLM([{"rating": "HOLD"}])).analyze(snapshot)

    class BrokenLLM:
        def generate_json(self, **kwargs):
            raise LLMGenerationError("DeepSeek returned invalid JSON")

    proposal = Trader(BrokenLLM()).propose(snapshot, research)

    assert proposal.action == "HOLD"
    assert "LLM 交易计划输出不可用" in proposal.reasoning
    assert proposal.stop_loss == 12.266666
    assert proposal.take_profit == 16.0
    assert proposal.position_ratio == 0.0
