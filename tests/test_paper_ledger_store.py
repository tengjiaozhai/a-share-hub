from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.paper_ledger.models import PaperBase, ScheduledJobLockRow
from src.paper_ledger.store import PaperLedgerStore


def setup_db():
    engine = create_engine("sqlite:///:memory:")
    PaperBase.metadata.create_all(engine)
    return Session(engine)


def test_get_or_create_account():
    session = setup_db()
    store = PaperLedgerStore(session)
    
    account = store.get_or_create_account("a", "auto", 1000000.0)
    assert account.market == "a"
    assert account.account_kind == "auto"
    assert account.initial_capital == 1000000.0
    
    # 再次获取应该返回同一个
    account2 = store.get_or_create_account("a", "auto")
    assert account2.account_id == account.account_id


def test_create_run():
    session = setup_db()
    store = PaperLedgerStore(session)
    
    account = store.get_or_create_account("a", "auto")
    run = store.create_run(
        account_id=account.account_id,
        market="a",
        trade_date=date(2026, 6, 6),
        run_source="auto",
        params={"capital": 1000000},
        watchlist=["600519.SH"],
    )
    assert run.status == "running"
    assert run.run_source == "auto"


def test_create_fill():
    session = setup_db()
    store = PaperLedgerStore(session)
    
    account = store.get_or_create_account("a", "auto")
    run = store.create_run(account.account_id, "a", date(2026, 6, 6), "auto", {}, [])
    fill = store.create_fill(run.run_id, account.account_id, "600519.SH", "BUY", 100, 1800.0)
    
    assert fill.symbol == "600519.SH"
    assert fill.action == "BUY"
    assert fill.quantity == 100
    assert fill.notional == 180000.0


def test_update_position():
    session = setup_db()
    store = PaperLedgerStore(session)
    
    account = store.get_or_create_account("a", "auto")
    store.update_position(account.account_id, "600519.SH", 100, 1800.0)
    
    position = store.get_position(account.account_id, "600519.SH")
    assert position.quantity == 100
    assert position.avg_cost == 1800.0
    
    # 更新持仓
    store.update_position(account.account_id, "600519.SH", 200, 1850.0)
    position = store.get_position(account.account_id, "600519.SH")
    assert position.quantity == 200


def test_nav_history():
    session = setup_db()
    store = PaperLedgerStore(session)
    
    account = store.get_or_create_account("a", "auto")
    store.create_nav_snapshot(account.account_id, date(2026, 6, 6), 1020000.0, 500000.0, 520000.0)
    store.create_nav_snapshot(account.account_id, date(2026, 6, 7), 1030000.0, 480000.0, 550000.0)
    
    history = store.get_nav_history(account.account_id, 10)
    assert len(history) == 2
    assert history[0].nav == 1030000.0  # 按日期倒序


def test_check_run_exists():
    session = setup_db()
    store = PaperLedgerStore(session)

    account = store.get_or_create_account("a", "auto")
    assert not store.check_run_exists("a", date(2026, 6, 6), "auto")

    store.create_run(account.account_id, "a", date(2026, 6, 6), "auto", {}, [])

    assert store.check_run_exists("a", date(2026, 6, 6), "auto")


def test_skipped_run_blocks_retry():
    session = setup_db()
    store = PaperLedgerStore(session)

    account = store.get_or_create_account("a", "auto")
    run = store.create_run(account.account_id, "a", date(2026, 6, 6), "auto", {}, [])
    store.update_run_status(run.run_id, "skipped", "market closed")

    assert store.check_run_exists("a", date(2026, 6, 6), "auto")


def test_failed_run_does_not_block_retry():
    session = setup_db()
    store = PaperLedgerStore(session)

    account = store.get_or_create_account("a", "auto")
    run = store.create_run(account.account_id, "a", date(2026, 6, 6), "auto", {}, [])
    store.update_run_status(run.run_id, "failed")

    assert not store.check_run_exists("a", date(2026, 6, 6), "auto")


def test_create_nav_snapshot_is_idempotent_by_account_date_source():
    session = setup_db()
    store = PaperLedgerStore(session)

    account = store.get_or_create_account("a", "auto")
    first = store.create_nav_snapshot(account.account_id, date(2026, 6, 6), 100.0, 50.0, 50.0, source="auto")
    second = store.create_nav_snapshot(account.account_id, date(2026, 6, 6), 101.0, 51.0, 50.0, source="auto")

    assert second.nav_id == first.nav_id
    assert len(store.get_nav_history(account.account_id, 10)) == 1


def test_acquire_job_lock_is_exclusive():
    session = setup_db()
    store = PaperLedgerStore(session)

    job_key = store.acquire_job_lock("daily_trading", "a", date(2026, 6, 6), lock_owner="worker-1")
    duplicate = store.acquire_job_lock("daily_trading", "a", date(2026, 6, 6), lock_owner="worker-2")

    assert job_key == "daily_trading:a:2026-06-06"
    assert duplicate is None

    store.finish_job_lock(job_key, "success")
    lock = session.execute(select(ScheduledJobLockRow)).scalar_one()
    assert lock.status == "success"
    assert lock.finished_at is not None


def test_expired_running_job_lock_can_be_reclaimed():
    session = setup_db()
    store = PaperLedgerStore(session)

    job_key = store.acquire_job_lock(
        "daily_trading",
        "a",
        date(2026, 6, 6),
        ttl_seconds=1,
        lock_owner="worker-1",
    )
    lock = session.execute(select(ScheduledJobLockRow)).scalar_one()
    lock.expires_at = datetime.utcnow() - timedelta(seconds=1)
    session.commit()
    session.expunge(lock)

    reclaimed = store.acquire_job_lock("daily_trading", "a", date(2026, 6, 6), lock_owner="worker-2")

    assert reclaimed == job_key
    lock = session.execute(select(ScheduledJobLockRow)).scalar_one()
    assert lock.lock_owner == "worker-2"
    assert lock.status == "running"
    assert lock.finished_at is None
