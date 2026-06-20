from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.paper_ledger.backfill import backfill_recent_days, needs_backfill
from src.paper_ledger.models import PaperBase
from src.core.tenant import TenantContext
from src.paper_ledger.store import PaperLedgerStore

TEST_USER_ID = "test-user"

class FixedCalendar:
    def __init__(self, days):
        self.days = days

    def recent_trading_days(self, market, end_date, count):
        return self.days[-count:]

def _make_store():
    engine = create_engine("sqlite:///:memory:")
    PaperBase.metadata.create_all(engine)
    return Session(engine)

def test_backfill_creates_nav_history():
    session = _make_store()
    store = PaperLedgerStore(session, TenantContext("test-user"))
    days = [
        date(2026, 6, 15),
        date(2026, 6, 16),
        date(2026, 6, 17),
        date(2026, 6, 18),
        date(2026, 6, 22),
    ]

    completed = backfill_recent_days(store, "a", days=5, calendar=FixedCalendar(days), )
    assert completed == 5

    account = store.get_or_create_account(market="a", account_kind="auto")
    history = store.get_nav_history(account_id=account.account_id, days=10)
    assert len(history) == 5
    assert {row.trade_date for row in history} == set(days)

def test_backfill_skips_existing_dates():
    session = _make_store()
    store = PaperLedgerStore(session, TenantContext("test-user"))
    days = [
        date(2026, 6, 15),
        date(2026, 6, 16),
        date(2026, 6, 17),
        date(2026, 6, 18),
        date(2026, 6, 22),
    ]
    calendar = FixedCalendar(days)

    backfill_recent_days(store, "a", days=5, calendar=calendar, )
    completed = backfill_recent_days(store, "a", days=5, calendar=calendar, )
    assert completed == 0

def test_backfill_returns_zero_when_fully_filled():
    session = _make_store()
    store = PaperLedgerStore(session, TenantContext("test-user"))

    completed = backfill_recent_days(
        store,
        "us",
        days=3,
        calendar=FixedCalendar([date(2026, 6, 15), date(2026, 6, 16), date(2026, 6, 17)]),
        )
    assert completed == 3

def test_needs_backfill_true_when_empty():
    session = _make_store()
    store = PaperLedgerStore(session, TenantContext("test-user"))
    assert needs_backfill(store, "a", ) is True

def test_needs_backfill_false_after_running():
    session = _make_store()
    store = PaperLedgerStore(session, TenantContext("test-user"))
    backfill_recent_days(
        store,
        "a",
        days=3,
        calendar=FixedCalendar([date(2026, 6, 15), date(2026, 6, 16), date(2026, 6, 17)]),
        )
    assert needs_backfill(store, "a", ) is False
