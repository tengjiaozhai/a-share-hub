import pytest
from sqlalchemy import create_engine

from src.alpha.portfolio_service import AlphaPortfolioService
from src.alpha.report_service import AlphaPortfolioReportService
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def _bootstrap_store(tmp_path) -> RuntimeStore:
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    return RuntimeStore(engine)


def _seed_holdings(store: RuntimeStore, price_map: dict[str, float] | None = None) -> None:
    ticket_id = store.insert_alpha_ticket(
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="phase2 seed",
        suggested_quantity=2.0,
        suggested_limit_price=200.0,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    store.insert_alpha_manual_fill(
        ticket_id=ticket_id,
        operator_id="trader-01",
        executed_quantity=2.0,
        executed_price=200.0,
        notes="buy fill",
    )
    AlphaPortfolioService(store).rebuild_from_manual_fills(
        opening_cash=10_000.0,
        price_map=price_map or {"AAPLx": 210.0},
    )


def _patched_shadow_provider(_store):
    def _provider(latest_workbench: dict | None, symbol: str) -> dict:
        return {"action": "HOLD", "confidence": 0.6, "reason": "shadow says hold"}

    return _provider


def _no_data_backtest_provider(_store):
    def _provider(symbol: str, window: str, opening_cash: float) -> dict:
        return {
            "status": "no_data",
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "trade_count": 0,
            "score": "N/A",
        }

    return _provider


def test_generate_report_with_held_positions(tmp_path):
    store = _bootstrap_store(tmp_path)
    _seed_holdings(store)

    service = AlphaPortfolioReportService(
        store=store,
        shadow_opinion_provider=_patched_shadow_provider(store),
        backtest_provider=_no_data_backtest_provider(store),
    )

    report = service.generate_report(
        {
            "symbols": [],
            "include_shadow": True,
            "include_backtest": True,
            "backtest_window": "60d",
            "opening_cash": 10_000.0,
        }
    )

    assert "generated_at" in report
    assert "portfolio_snapshot" in report
    assert len(report["items"]) == 1

    item = report["items"][0]
    assert item["symbol"] == "AAPLx"
    assert item["quantity"] == 2.0
    assert item["avg_cost"] == 200.0
    assert item["mark_price"] == 210.0
    assert item["unrealized_pnl"] == 20.0
    assert item["unrealized_pnl_pct"] == pytest.approx(0.05)

    assert item["fill_summary"]["count"] == 1
    assert item["fill_summary"]["buy_quantity"] == 2.0
    assert item["fill_summary"]["sell_quantity"] == 0.0


def test_generate_report_empty_symbols_uses_all_holdings(tmp_path):
    store = _bootstrap_store(tmp_path)

    buy_id = store.insert_alpha_ticket(
        asset_symbol="AAPLx",
        underlying_symbol="AAPL",
        action="BUY",
        thesis="open",
        suggested_quantity=2.0,
        suggested_limit_price=200.0,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    other_id = store.insert_alpha_ticket(
        asset_symbol="TSLAx",
        underlying_symbol="TSLA",
        action="BUY",
        thesis="open",
        suggested_quantity=1.0,
        suggested_limit_price=100.0,
        expires_at="2026-06-01T16:00:00+08:00",
    )
    store.insert_alpha_manual_fill(
        ticket_id=buy_id, operator_id="trader-01",
        executed_quantity=2.0, executed_price=200.0, notes="buy AAPLx",
    )
    store.insert_alpha_manual_fill(
        ticket_id=other_id, operator_id="trader-01",
        executed_quantity=1.0, executed_price=100.0, notes="buy TSLAx",
    )
    AlphaPortfolioService(store).rebuild_from_manual_fills(
        opening_cash=10_000.0,
        price_map={"AAPLx": 210.0, "TSLAx": 105.0},
    )

    service = AlphaPortfolioReportService(
        store=store,
        shadow_opinion_provider=_patched_shadow_provider(store),
        backtest_provider=_no_data_backtest_provider(store),
    )
    report = service.generate_report(
        {"symbols": [], "opening_cash": 10_000.0}
    )

    symbols = {item["symbol"] for item in report["items"]}
    assert symbols == {"AAPLx", "TSLAx"}


def test_generate_report_filters_to_requested_symbols(tmp_path):
    store = _bootstrap_store(tmp_path)

    buy_id = store.insert_alpha_ticket(
        asset_symbol="AAPLx", underlying_symbol="AAPL",
        action="BUY", thesis="open", suggested_quantity=2.0,
        suggested_limit_price=200.0, expires_at="2026-06-01T16:00:00+08:00",
    )
    other_id = store.insert_alpha_ticket(
        asset_symbol="TSLAx", underlying_symbol="TSLA",
        action="BUY", thesis="open", suggested_quantity=1.0,
        suggested_limit_price=100.0, expires_at="2026-06-01T16:00:00+08:00",
    )
    store.insert_alpha_manual_fill(
        ticket_id=buy_id, operator_id="trader-01",
        executed_quantity=2.0, executed_price=200.0, notes="buy",
    )
    store.insert_alpha_manual_fill(
        ticket_id=other_id, operator_id="trader-01",
        executed_quantity=1.0, executed_price=100.0, notes="buy",
    )
    AlphaPortfolioService(store).rebuild_from_manual_fills(
        opening_cash=10_000.0,
        price_map={"AAPLx": 210.0, "TSLAx": 105.0},
    )

    service = AlphaPortfolioReportService(
        store=store,
        shadow_opinion_provider=_patched_shadow_provider(store),
        backtest_provider=_no_data_backtest_provider(store),
    )
    report = service.generate_report(
        {"symbols": ["AAPLx"], "opening_cash": 10_000.0}
    )

    assert len(report["items"]) == 1
    assert report["items"][0]["symbol"] == "AAPLx"


def test_generate_report_recommendation_action_enum(tmp_path):
    store = _bootstrap_store(tmp_path)
    _seed_holdings(store)

    service = AlphaPortfolioReportService(
        store=store,
        shadow_opinion_provider=_patched_shadow_provider(store),
        backtest_provider=_no_data_backtest_provider(store),
    )
    report = service.generate_report(
        {"symbols": [], "opening_cash": 10_000.0}
    )

    valid_actions = {"HOLD", "ADD", "REDUCE", "EXIT", "WATCH"}
    for item in report["items"]:
        assert item["recommendation"]["action"] in valid_actions
        assert 0.0 <= item["recommendation"]["confidence"] <= 1.0


def test_generate_report_handles_no_backtest_data(tmp_path):
    store = _bootstrap_store(tmp_path)
    _seed_holdings(store)

    service = AlphaPortfolioReportService(
        store=store,
        shadow_opinion_provider=_patched_shadow_provider(store),
        backtest_provider=_no_data_backtest_provider(store),
    )
    report = service.generate_report(
        {"symbols": [], "opening_cash": 10_000.0}
    )

    backtest = report["items"][0]["backtest"]
    assert backtest["status"] == "no_data"
    assert len(report["items"]) == 1


def test_generate_report_pnl_calculation(tmp_path):
    store = _bootstrap_store(tmp_path)

    ticket_id = store.insert_alpha_ticket(
        asset_symbol="AAPLx", underlying_symbol="AAPL",
        action="BUY", thesis="open", suggested_quantity=4.0,
        suggested_limit_price=100.0, expires_at="2026-06-01T16:00:00+08:00",
    )
    store.insert_alpha_manual_fill(
        ticket_id=ticket_id, operator_id="trader-01",
        executed_quantity=4.0, executed_price=100.0, notes="buy",
    )
    AlphaPortfolioService(store).rebuild_from_manual_fills(
        opening_cash=10_000.0,
        price_map={"AAPLx": 120.0},
    )

    service = AlphaPortfolioReportService(
        store=store,
        shadow_opinion_provider=_patched_shadow_provider(store),
        backtest_provider=_no_data_backtest_provider(store),
    )
    report = service.generate_report(
        {"symbols": [], "opening_cash": 10_000.0}
    )

    item = report["items"][0]
    assert item["quantity"] == 4.0
    assert item["avg_cost"] == 100.0
    assert item["mark_price"] == 120.0
    assert item["unrealized_pnl"] == 80.0
    assert item["unrealized_pnl_pct"] == pytest.approx(0.20)


def test_generate_report_floating_loss_triggers_exit_or_reduce(tmp_path):
    store = _bootstrap_store(tmp_path)

    ticket_id = store.insert_alpha_ticket(
        asset_symbol="AAPLx", underlying_symbol="AAPL",
        action="BUY", thesis="open", suggested_quantity=2.0,
        suggested_limit_price=200.0, expires_at="2026-06-01T16:00:00+08:00",
    )
    store.insert_alpha_manual_fill(
        ticket_id=ticket_id, operator_id="trader-01",
        executed_quantity=2.0, executed_price=200.0, notes="buy",
    )
    AlphaPortfolioService(store).rebuild_from_manual_fills(
        opening_cash=10_000.0,
        price_map={"AAPLx": 180.0},
    )

    service = AlphaPortfolioReportService(
        store=store,
        shadow_opinion_provider=_patched_shadow_provider(store),
        backtest_provider=_no_data_backtest_provider(store),
    )
    report = service.generate_report(
        {"symbols": [], "opening_cash": 10_000.0}
    )

    item = report["items"][0]
    assert item["unrealized_pnl_pct"] <= -0.08
    assert item["recommendation"]["action"] in {"EXIT", "REDUCE"}


def test_build_recommendation_is_pure_and_picks_exit_for_severe_loss():
    from src.alpha.report_service import _build_recommendation

    position = {"quantity": 2.0, "unrealized_pnl_pct": -0.10}
    shadow: dict = {}
    backtest = {"status": "no_data", "score": "N/A", "max_drawdown": 0.0}

    rec = _build_recommendation(position, shadow, backtest)
    assert rec["action"] in {"EXIT", "REDUCE"}
    assert 0.0 <= rec["confidence"] <= 1.0
    assert isinstance(rec["reason"], str)


def test_build_shadow_section_returns_empty_when_no_workbench():
    from src.alpha.report_service import _build_shadow_section

    result = _build_shadow_section(None, "AAPLx")
    assert result == {"action": "UNKNOWN", "confidence": 0, "reason": "无最近模拟交易"}
