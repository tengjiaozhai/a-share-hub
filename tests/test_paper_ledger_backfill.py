from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.paper_ledger.models import PaperBase
from src.paper_ledger.store import PaperLedgerStore
from src.paper_ledger.backfill import backfill_recent_days, needs_backfill


def _make_store():
    engine = create_engine("sqlite:///:memory:")
    PaperBase.metadata.create_all(engine)
    return Session(engine)


def test_backfill_creates_nav_history():
    session = _make_store()
    store = PaperLedgerStore(session)

    completed = backfill_recent_days(store, "a", days=5)
    assert completed == 5

    account = store.get_or_create_account("a", "auto")
    history = store.get_nav_history(account.account_id, days=10)
    assert len(history) == 5


def test_backfill_skips_existing_dates():
    session = _make_store()
    store = PaperLedgerStore(session)

    backfill_recent_days(store, "a", days=5)
    completed = backfill_recent_days(store, "a", days=5)
    assert completed == 0


def test_backfill_returns_zero_when_fully_filled():
    session = _make_store()
    store = PaperLedgerStore(session)

    completed = backfill_recent_days(store, "us", days=10)
    assert completed == 10


def test_needs_backfill_true_when_empty():
    session = _make_store()
    store = PaperLedgerStore(session)
    assert needs_backfill(store, "a") is True


def test_needs_backfill_false_after_running():
    session = _make_store()
    store = PaperLedgerStore(session)
    backfill_recent_days(store, "a", days=3)
    assert needs_backfill(store, "a") is False
