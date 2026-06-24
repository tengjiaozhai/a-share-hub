from unittest.mock import MagicMock

from src.alpha.analysis_agents import ResearchManager, Trader
from src.alpha.analysis_models import AnalysisSnapshot, ResearchPlan, TraderProposal


def _make_snapshot() -> AnalysisSnapshot:
    return AnalysisSnapshot(
        symbol="MU.US",
        market="us",
        currency="USD",
        as_of="2026-06-22",
        quantity=0.022,
        weighted_avg_cost=1006.68,
        close=1133.99,
        market_value=24.95,
        unrealized_pnl=2.79,
        unrealized_pnl_ratio=0.126,
        position_ratio=0.01,
        stop_loss_ratio=-0.08,
        take_profit_ratio=0.20,
        technical={"ma20": 1100, "ma60": 1050},
        fundamentals={"status": "ok", "pe_ratio": 15.2},
        news={},
        data_quality={},
    )


def test_research_manager_uses_model_research():
    mock_llm = MagicMock()
    mock_llm.generate_json.return_value = {
        "rating": "HOLD",
        "thesis": "test",
        "technical_view": "test",
        "fundamental_view": "test",
        "sentiment_view": "test",
        "catalysts": [],
        "risks": ["test"],
        "confidence": 0.5,
        "data_gaps": [],
    }

    rm = ResearchManager(mock_llm, model="deepseek-v4-pro")
    rm.analyze(_make_snapshot())

    call_kwargs = mock_llm.generate_json.call_args[1]
    assert call_kwargs["model"] == "deepseek-v4-pro"


def test_trader_uses_model_trader():
    mock_llm = MagicMock()
    mock_llm.generate_json.return_value = {
        "action": "HOLD",
        "reasoning": "test",
        "entry_low": 1100,
        "entry_high": 1200,
        "stop_loss": 1000,
        "take_profit": 1300,
        "position_ratio": 0.0,
    }

    research = ResearchPlan(
        rating="HOLD",
        thesis="test",
        technical_view="test",
        fundamental_view="test",
        sentiment_view="test",
        catalysts=[],
        risks=["test"],
        confidence=0.5,
        data_gaps=[],
    )

    t = Trader(mock_llm, model="deepseek-v4-flash")
    t.propose(_make_snapshot(), research)

    call_kwargs = mock_llm.generate_json.call_args[1]
    assert call_kwargs["model"] == "deepseek-v4-flash"


def test_research_manager_default_model():
    mock_llm = MagicMock()
    mock_llm.generate_json.return_value = {
        "rating": "HOLD",
        "thesis": "test",
        "technical_view": "test",
        "fundamental_view": "test",
        "sentiment_view": "test",
        "catalysts": [],
        "risks": ["test"],
        "confidence": 0.5,
        "data_gaps": [],
    }

    rm = ResearchManager(mock_llm)
    rm.analyze(_make_snapshot())

    call_kwargs = mock_llm.generate_json.call_args[1]
    assert call_kwargs["model"] is None
