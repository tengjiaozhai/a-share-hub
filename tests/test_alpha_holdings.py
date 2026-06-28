from sqlalchemy import create_engine

from src.alpha.portfolio_service import AlphaPortfolioService
from src.core.tenant import TenantContext
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def _make_store(tmp_path, user_id="test-user"):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    return RuntimeStore(engine, TenantContext(user_id))


def _create_ticket(store, asset_symbol, action, quantity, limit_price):
    return store.insert_alpha_ticket(
        asset_symbol=asset_symbol,
        underlying_symbol=asset_symbol.replace("x", ""),
        action=action,
        thesis="test thesis",
        suggested_quantity=quantity,
        suggested_limit_price=limit_price,
        expires_at="2026-06-01T16:00:00+08:00",
    )


def test_record_fill_rebuilds_positions(tmp_path):
    store = _make_store(tmp_path)

    ticket_id = _create_ticket(store, "AAPLx", "BUY", 100, 12.0)
    store.insert_alpha_manual_fill(
        ticket_id=ticket_id,
        operator_id="trader-01",
        executed_quantity=50,
        executed_price=10.0,
        notes="first buy",
    )
    store.insert_alpha_manual_fill(
        ticket_id=ticket_id,
        operator_id="trader-01",
        executed_quantity=50,
        executed_price=12.0,
        notes="second buy",
    )

    service = AlphaPortfolioService(store)
    summary = service.rebuild_from_manual_fills(
        opening_cash=10000.0,
        price_map={"AAPLx": 11.0},
        ticket_lookup={ticket_id: {"asset_symbol": "AAPLx", "action": "BUY"}},
    )

    assert len(summary["positions"]) == 1
    pos = summary["positions"][0]
    assert pos["symbol"] == "AAPLx"
    assert pos["quantity"] == 100
    assert pos["avg_cost"] == 11.0
    assert pos["mark_price"] == 11.0
    assert pos["unrealized_pnl"] == 0.0
    assert round(summary["cash_balance"], 2) == 10000.0 - 50 * 10 - 50 * 12
    assert summary["realized_pnl"] == 0.0


def test_partial_sell_calculates_realized_pnl(tmp_path):
    store = _make_store(tmp_path)

    buy_ticket = _create_ticket(store, "AAPLx", "BUY", 100, 10.0)
    sell_ticket = _create_ticket(store, "AAPLx", "SELL", 30, 15.0)
    store.insert_alpha_manual_fill(
        ticket_id=buy_ticket,
        operator_id="trader-01",
        executed_quantity=100,
        executed_price=10.0,
        notes="buy",
    )
    store.insert_alpha_manual_fill(
        ticket_id=sell_ticket,
        operator_id="trader-01",
        executed_quantity=30,
        executed_price=15.0,
        notes="sell",
    )

    service = AlphaPortfolioService(store)
    summary = service.rebuild_from_manual_fills(
        opening_cash=10000.0,
        price_map={"AAPLx": 12.0},
        ticket_lookup={
            buy_ticket: {"asset_symbol": "AAPLx", "action": "BUY"},
            sell_ticket: {"asset_symbol": "AAPLx", "action": "SELL"},
        },
    )

    assert round(summary["realized_pnl"], 2) == (15.0 - 10.0) * 30
    pos = summary["positions"][0]
    assert pos["quantity"] == 70
    assert pos["avg_cost"] == 10.0
    assert pos["unrealized_pnl"] == (12.0 - 10.0) * 70


def test_full_sell_removes_position(tmp_path):
    store = _make_store(tmp_path)

    buy_ticket = _create_ticket(store, "AAPLx", "BUY", 100, 10.0)
    sell_ticket = _create_ticket(store, "AAPLx", "SELL", 100, 12.0)
    store.insert_alpha_manual_fill(
        ticket_id=buy_ticket,
        operator_id="trader-01",
        executed_quantity=100,
        executed_price=10.0,
        notes="buy",
    )
    store.insert_alpha_manual_fill(
        ticket_id=sell_ticket,
        operator_id="trader-01",
        executed_quantity=100,
        executed_price=12.0,
        notes="sell all",
    )

    service = AlphaPortfolioService(store)
    summary = service.rebuild_from_manual_fills(
        opening_cash=10000.0,
        price_map={},
        ticket_lookup={
            buy_ticket: {"asset_symbol": "AAPLx", "action": "BUY"},
            sell_ticket: {"asset_symbol": "AAPLx", "action": "SELL"},
        },
    )

    assert len(summary["positions"]) == 0
    assert round(summary["realized_pnl"], 2) == (12.0 - 10.0) * 100
    assert round(summary["cash_balance"], 2) == 10000.0 - 100 * 10 + 100 * 12


def test_portfolio_query_groups_saved_holdings_by_symbol(tmp_path):
    store = _make_store(tmp_path)

    store.insert_alpha_holdings_entry(
        symbol="AAPLx",
        buy_date="2026-06-01",
        buy_price=10.0,
        quantity=50,
    )
    store.insert_alpha_holdings_entry(
        symbol="GOOGx",
        buy_date="2026-06-02",
        buy_price=100.0,
        quantity=30,
    )
    store.replace_alpha_positions([
        {"symbol": "AAPLx", "quantity": 50, "avg_cost": 10.0, "mark_price": 11.0},
        {"symbol": "GOOGx", "quantity": 30, "avg_cost": 100.0, "mark_price": 105.0},
    ])
    store.insert_alpha_portfolio_snapshot(
        cash_balance=10000.0 - 50 * 10 - 30 * 100,
        realized_pnl=0.0,
        unrealized_pnl=50 * 1.0 + 30 * 5.0,
        nav=10000.0 - 50 * 10 - 30 * 100 + 50 * 11 + 30 * 105,
    )

    service = AlphaPortfolioService(store)
    portfolio = service.load_portfolio()

    assert "fills_by_symbol" in portfolio
    assert "AAPLx" in portfolio["fills_by_symbol"]
    assert "GOOGx" in portfolio["fills_by_symbol"]
    assert len(portfolio["fills_by_symbol"]["AAPLx"]) == 1
    assert len(portfolio["fills_by_symbol"]["GOOGx"]) == 1
    assert portfolio["fills_by_symbol"]["AAPLx"][0]["asset_symbol"] == "AAPLx"


def test_load_portfolio_prefers_saved_holdings_over_manual_fills(tmp_path):
    store = _make_store(tmp_path)

    ticket_id = _create_ticket(store, "LEGACYx", "BUY", 10, 9.0)
    store.insert_alpha_manual_fill(
        ticket_id=ticket_id,
        operator_id="trader-01",
        executed_quantity=10,
        executed_price=9.0,
        notes="legacy fill",
    )
    store.insert_alpha_holdings_entry(
        symbol="MSFT.US",
        buy_date="2026-06-18",
        buy_price=420.0,
        quantity=2.0,
    )
    store.replace_alpha_positions([
        {"symbol": "MSFT.US", "quantity": 2.0, "avg_cost": 420.0, "mark_price": 430.0},
    ])
    store.insert_alpha_portfolio_snapshot(
        cash_balance=0.0,
        realized_pnl=0.0,
        unrealized_pnl=20.0,
        nav=860.0,
    )

    portfolio = AlphaPortfolioService(store).load_portfolio()

    assert [fill["asset_symbol"] for fill in portfolio["fills"]] == ["MSFT.US"]


def test_portfolio_positions_include_unrealized_pnl(tmp_path):
    store = _make_store(tmp_path)

    store.replace_alpha_positions([
        {"symbol": "AAPLx", "quantity": 100, "avg_cost": 10.0, "mark_price": 12.0},
    ])
    store.insert_alpha_portfolio_snapshot(
        cash_balance=5000.0,
        realized_pnl=0.0,
        unrealized_pnl=200.0,
        nav=5200.0,
    )

    service = AlphaPortfolioService(store)
    portfolio = service.load_portfolio()

    assert len(portfolio["positions"]) == 1
    pos = portfolio["positions"][0]
    assert pos["symbol"] == "AAPLx"
    assert pos["unrealized_pnl"] == (12.0 - 10.0) * 100


def test_rebuild_with_multiple_symbols(tmp_path):
    store = _make_store(tmp_path)

    aapl_buy = _create_ticket(store, "AAPLx", "BUY", 50, 10.0)
    goog_buy = _create_ticket(store, "GOOGx", "BUY", 20, 100.0)
    aapl_sell = _create_ticket(store, "AAPLx", "SELL", 20, 12.0)
    store.insert_alpha_manual_fill(
        ticket_id=aapl_buy,
        operator_id="trader-01",
        executed_quantity=50,
        executed_price=10.0,
        notes="buy aapl",
    )
    store.insert_alpha_manual_fill(
        ticket_id=goog_buy,
        operator_id="trader-01",
        executed_quantity=20,
        executed_price=100.0,
        notes="buy goog",
    )
    store.insert_alpha_manual_fill(
        ticket_id=aapl_sell,
        operator_id="trader-01",
        executed_quantity=20,
        executed_price=12.0,
        notes="sell aapl partial",
    )

    service = AlphaPortfolioService(store)
    summary = service.rebuild_from_manual_fills(
        opening_cash=20000.0,
        price_map={"AAPLx": 11.0, "GOOGx": 105.0},
        ticket_lookup={
            aapl_buy: {"asset_symbol": "AAPLx", "action": "BUY"},
            goog_buy: {"asset_symbol": "GOOGx", "action": "BUY"},
            aapl_sell: {"asset_symbol": "AAPLx", "action": "SELL"},
        },
    )

    symbols = {p["symbol"] for p in summary["positions"]}
    assert symbols == {"AAPLx", "GOOGx"}
    aapl_pos = next(p for p in summary["positions"] if p["symbol"] == "AAPLx")
    goog_pos = next(p for p in summary["positions"] if p["symbol"] == "GOOGx")
    assert aapl_pos["quantity"] == 30
    assert aapl_pos["avg_cost"] == 10.0
    assert aapl_pos["unrealized_pnl"] == (11.0 - 10.0) * 30
    assert goog_pos["quantity"] == 20
    assert goog_pos["avg_cost"] == 100.0
    assert goog_pos["unrealized_pnl"] == (105.0 - 100.0) * 20
    assert round(summary["realized_pnl"], 2) == (12.0 - 10.0) * 20
    expected_cash = 20000.0 - 50 * 10 - 20 * 100 + 20 * 12
    assert round(summary["cash_balance"], 2) == expected_cash


def test_rebuild_portfolio_returns_full_view(tmp_path):
    store = _make_store(tmp_path)

    ticket_id = _create_ticket(store, "AAPLx", "BUY", 100, 10.0)
    store.insert_alpha_manual_fill(
        ticket_id=ticket_id,
        operator_id="trader-01",
        executed_quantity=100,
        executed_price=10.0,
        notes="buy",
    )

    service = AlphaPortfolioService(store)
    result = service.rebuild_portfolio(
        opening_cash=10000.0,
        price_map={"AAPLx": 11.0},
    )

    assert "snapshot" in result
    assert "positions" in result
    assert "fills" in result
    assert result["snapshot"]["nav"] == 10000.0 - 100 * 10 + 100 * 11
    assert result["positions"][0]["unrealized_pnl"] == (11.0 - 10.0) * 100
