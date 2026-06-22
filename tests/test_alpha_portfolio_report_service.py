import pytest
from sqlalchemy import create_engine

from src.alpha.analysis_agents import AnalysisAgentError
from src.alpha.analysis_models import AnalysisSnapshot, ResearchPlan, TraderProposal
from src.alpha.portfolio_service import AlphaPortfolioService
from src.alpha.report_service import (
    AlphaPortfolioReportService,
    _build_backtest_section,
    _build_fill_summary,
    _build_positions_from_holdings_entries,
    normalize_report_positions,
    normalize_report_symbol,
)
from src.core.tenant import TenantContext
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore

TEST_USER_ID = "test-user"


def _bootstrap_store(tmp_path) -> RuntimeStore:
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    return RuntimeStore(engine, TenantContext("test-user"))


def _no_data_backtest_provider(symbol: str, window: str, opening_cash: float) -> dict:
    return {
        "status": "no_data",
        "total_return": 0.0,
        "max_drawdown": 0.0,
        "trade_count": 0,
        "score": "N/A",
    }


SNAPSHOT = AnalysisSnapshot(
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
        "volume_ratio_20": 1.2,
        "bar_count": 61,
        "reclaimed_ma20": True,
    },
    fundamentals={"status": "ok", "pe_ratio": 18.2},
    news={"status": "unavailable", "items": []},
    data_quality={"status": "partial", "missing": ["news"]},
)
BULLISH_RESEARCH = ResearchPlan(
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
BUY_PROPOSAL = TraderProposal(
    action="BUY",
    reasoning="研究方向偏多且位置未追高",
    entry_low=15.8,
    entry_high=16.2,
    stop_loss=15.0,
    take_profit=19.0,
    position_ratio=0.1,
)


class FakeSnapshotBuilder:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def build(self, **kwargs):
        return self.snapshot


class FakeResearchManager:
    def __init__(self, research):
        self.research = research

    def analyze(self, snapshot):
        return self.research


class FailingResearchManager:
    def __init__(self, message):
        self.message = message

    def analyze(self, snapshot):
        raise AnalysisAgentError(self.message)


class FakeTrader:
    def __init__(self, proposal):
        self.proposal = proposal

    def propose(self, snapshot, research):
        return self.proposal


def _seed_analysis_holding(store):
    store.insert_alpha_holdings_entry(
        symbol="600703.SH",
        buy_date="2026-06-01",
        buy_price=13.333333,
        quantity=300,
    )


def test_report_runs_snapshot_research_trader_risk_and_persists(tmp_path):
    store = _bootstrap_store(tmp_path)
    _seed_analysis_holding(store)
    service = AlphaPortfolioReportService(
        store=store,
        snapshot_builder=FakeSnapshotBuilder(SNAPSHOT),
        research_manager=FakeResearchManager(BULLISH_RESEARCH),
        trader=FakeTrader(BUY_PROPOSAL),
        model_name="deepseek-v4-pro",
        max_position_ratio=0.2,
    )
    report = service.generate_report({"symbols": ["600703.SH"], "backtest_window": "60d"})

    item = report["items"][0]
    assert item["status"] == "completed"
    assert item["research"]["rating"] == "OVERWEIGHT"
    assert item["trader"]["action"] == "BUY"
    assert item["risk"]["action"] == "ADD"
    assert store.get_alpha_analysis_run(item["run_id"])["symbol"] == "600703.SH"


def test_report_persists_visible_failure_without_mock_decision(tmp_path):
    store = _bootstrap_store(tmp_path)
    _seed_analysis_holding(store)
    service = AlphaPortfolioReportService(
        store=store,
        snapshot_builder=FakeSnapshotBuilder(SNAPSHOT),
        research_manager=FailingResearchManager("DeepSeek timeout"),
        trader=FakeTrader(BUY_PROPOSAL),
        model_name="deepseek-v4-pro",
        max_position_ratio=0.2,
    )
    item = service.generate_report({"symbols": ["600703.SH"]})["items"][0]

    assert item["status"] == "failed"
    assert item["research"] is None
    assert item["trader"] is None
    assert item["risk"] is None
    assert "DeepSeek timeout" in item["error"]


class RaisingSnapshotBuilder:
    def __init__(self, exception):
        self.exception = exception

    def build(self, **kwargs):
        raise self.exception


def test_report_catches_unexpected_snapshot_exception(tmp_path):
    store = _bootstrap_store(tmp_path)
    _seed_analysis_holding(store)
    service = AlphaPortfolioReportService(
        store=store,
        snapshot_builder=RaisingSnapshotBuilder(RuntimeError("yfinance rate limited")),
        research_manager=FakeResearchManager(BULLISH_RESEARCH),
        trader=FakeTrader(BUY_PROPOSAL),
        model_name="deepseek-v4-pro",
        max_position_ratio=0.2,
    )
    item = service.generate_report({"symbols": ["600703.SH"]})["items"][0]

    assert item["status"] == "failed"
    assert item["snapshot"] is None
    assert item["research"] is None
    assert "yfinance rate limited" in item["error"]


def test_normalize_report_symbol_a_share():
    assert normalize_report_symbol("600519") == "600519.SH"


def test_normalize_report_symbol_us():
    assert normalize_report_symbol("AAPL") == "AAPL.US"


def test_normalize_report_symbol_already_suffixed():
    assert normalize_report_symbol("AAPL.US") == "AAPL.US"


def test_normalize_report_positions_drops_invalid():
    result = normalize_report_positions([
        {"symbol": "AAPL", "lots": [{"buy_date": "", "buy_price": 100, "quantity": 1}]},
        {"symbol": "MSFT", "lots": [{"buy_date": "2026-01-01", "buy_price": 200, "quantity": 2}]},
    ])
    assert len(result) == 2
    assert result[0]["symbol"] == "AAPL.US"
    assert result[0]["lots"] == []
    assert result[1]["symbol"] == "MSFT.US"
    assert len(result[1]["lots"]) == 1


def test_build_positions_from_holdings_entries_groups():
    entries = [
        {"symbol": "600519", "buy_date": "2026-01-01", "buy_price": 100, "quantity": 100},
        {"symbol": "600519", "buy_date": "2026-01-02", "buy_price": 110, "quantity": 200},
    ]
    result = _build_positions_from_holdings_entries(entries)
    assert len(result) == 1
    assert result[0]["symbol"] == "600519.SH"
    assert len(result[0]["lots"]) == 2


def test_build_fill_summary_counts():
    fills = [
        {"executed_quantity": 10, "action": "BUY"},
        {"executed_quantity": 3, "action": "SELL"},
        {"executed_quantity": 5, "action": "BUY"},
    ]
    result = _build_fill_summary(fills)
    assert result["count"] == 3
    assert result["buy_quantity"] == 15
    assert result["sell_quantity"] == 3


def test_build_backtest_section_no_data():
    result = _build_backtest_section("600519.SH", "60d", 10000.0, _no_data_backtest_provider)
    assert result["status"] == "no_data"
    assert result["trade_count"] == 0
