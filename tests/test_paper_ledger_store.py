from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.tenant import TenantContext
from src.paper_ledger.models import PaperBase, ScheduledJobLockRow
from src.paper_ledger.store import PaperLedgerStore

TEST_USER_ID = "test-user"

def setup_db():
    engine = create_engine("sqlite:///:memory:")
    PaperBase.metadata.create_all(engine)
    return Session(engine)

def test_get_or_create_account():
    session = setup_db()
    store = PaperLedgerStore(session, TenantContext("test-user"))

    account = store.get_or_create_account(market="a", account_kind="auto", initial_capital=1000000.0)
    assert account.market == "a"
    assert account.account_kind == "auto"
    assert account.initial_capital == 1000000.0

    # 再次获取应该返回同一个
    account2 = store.get_or_create_account(market="a", account_kind="auto")
    assert account2.account_id == account.account_id

def test_create_run():
    session = setup_db()
    store = PaperLedgerStore(session, TenantContext("test-user"))

    account = store.get_or_create_account(market="a", account_kind="auto")
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
    store = PaperLedgerStore(session, TenantContext("test-user"))

    account = store.get_or_create_account(market="a", account_kind="auto")
    run = store.create_run(
        account_id=account.account_id,
        market="a",
        trade_date=date(2026, 6, 6),
        run_source="auto",
        params={},
        watchlist=[],
    )
    fill = store.create_fill(
        run_id=run.run_id,
        account_id=account.account_id,
        symbol="600519.SH",
        action="BUY",
        quantity=100,
        price=1800.0,
    )

    assert fill.symbol == "600519.SH"
    assert fill.action == "BUY"
    assert fill.quantity == 100
    assert fill.notional == 180000.0

def test_update_position():
    session = setup_db()
    store = PaperLedgerStore(session, TenantContext("test-user"))

    account = store.get_or_create_account(market="a", account_kind="auto")
    store.update_position(
        account_id=account.account_id,
        symbol="600519.SH",
        quantity=100,
        avg_cost=1800.0,
    )

    position = store.get_position(account_id=account.account_id, symbol="600519.SH")
    assert position.quantity == 100
    assert position.avg_cost == 1800.0

    # 更新持仓
    store.update_position(
        account_id=account.account_id,
        symbol="600519.SH",
        quantity=200,
        avg_cost=1850.0,
    )
    position = store.get_position(account_id=account.account_id, symbol="600519.SH")
    assert position.quantity == 200

def test_nav_history():
    session = setup_db()
    store = PaperLedgerStore(session, TenantContext("test-user"))

    account = store.get_or_create_account(market="a", account_kind="auto")
    store.create_nav_snapshot(
        account_id=account.account_id,
        trade_date=date(2026, 6, 6),
        nav=1020000.0,
        cash=500000.0,
        positions_value=520000.0,
    )
    store.create_nav_snapshot(
        account_id=account.account_id,
        trade_date=date(2026, 6, 7),
        nav=1030000.0,
        cash=480000.0,
        positions_value=550000.0,
    )

    history = store.get_nav_history(account_id=account.account_id, days=10)
    assert len(history) == 2
    assert history[0].nav == 1030000.0  # 按日期倒序

def test_check_run_exists():
    session = setup_db()
    store = PaperLedgerStore(session, TenantContext("test-user"))

    account = store.get_or_create_account(market="a", account_kind="auto")
    assert not store.check_run_exists(
        market="a", trade_date=date(2026, 6, 6), run_source="auto"
    )

    store.create_run(
        account_id=account.account_id,
        market="a",
        trade_date=date(2026, 6, 6),
        run_source="auto",
        params={},
        watchlist=[],
    )

    assert store.check_run_exists(
        market="a", trade_date=date(2026, 6, 6), run_source="auto"
    )

def test_skipped_run_blocks_retry():
    session = setup_db()
    store = PaperLedgerStore(session, TenantContext("test-user"))

    account = store.get_or_create_account(market="a", account_kind="auto")
    run = store.create_run(
        account_id=account.account_id,
        market="a",
        trade_date=date(2026, 6, 6),
        run_source="auto",
        params={},
        watchlist=[],
    )
    store.update_run_status(run.run_id, "skipped", "market closed")

    assert store.check_run_exists(
        market="a", trade_date=date(2026, 6, 6), run_source="auto"
    )

def test_failed_run_does_not_block_retry():
    session = setup_db()
    store = PaperLedgerStore(session, TenantContext("test-user"))

    account = store.get_or_create_account(market="a", account_kind="auto")
    run = store.create_run(
        account_id=account.account_id,
        market="a",
        trade_date=date(2026, 6, 6),
        run_source="auto",
        params={},
        watchlist=[],
    )
    store.update_run_status(run.run_id, "failed")

    assert not store.check_run_exists(
        market="a", trade_date=date(2026, 6, 6), run_source="auto"
    )

def test_create_nav_snapshot_is_idempotent_by_account_date_source():
    session = setup_db()
    store = PaperLedgerStore(session, TenantContext("test-user"))

    account = store.get_or_create_account(market="a", account_kind="auto")
    first = store.create_nav_snapshot(
        account_id=account.account_id,
        trade_date=date(2026, 6, 6),
        nav=100.0,
        cash=50.0,
        positions_value=50.0,
        source="auto",
    )
    second = store.create_nav_snapshot(
        account_id=account.account_id,
        trade_date=date(2026, 6, 6),
        nav=101.0,
        cash=51.0,
        positions_value=50.0,
        source="auto",
    )

    assert second.nav_id == first.nav_id
    assert len(store.get_nav_history(account_id=account.account_id, days=10)) == 1

def test_acquire_job_lock_is_exclusive():
    session = setup_db()
    store = PaperLedgerStore(session, TenantContext("test-user"))

    job_key = store.acquire_job_lock(
        job_name="daily_trading",
        market="a",
        trade_date=date(2026, 6, 6),
        lock_owner="worker-1",
    )
    duplicate = store.acquire_job_lock(
        job_name="daily_trading",
        market="a",
        trade_date=date(2026, 6, 6),
        lock_owner="worker-2",
    )

    assert job_key == "daily_trading:a:2026-06-06"
    assert duplicate is None

    store.finish_job_lock(job_key, "success")
    lock = session.execute(select(ScheduledJobLockRow)).scalar_one()
    assert lock.status == "success"
    assert lock.finished_at is not None

def test_expired_running_job_lock_can_be_reclaimed():
    session = setup_db()
    store = PaperLedgerStore(session, TenantContext("test-user"))

    job_key = store.acquire_job_lock(
        job_name="daily_trading",
        market="a",
        trade_date=date(2026, 6, 6),
        ttl_seconds=1,
        lock_owner="worker-1",
    )
    lock = session.execute(select(ScheduledJobLockRow)).scalar_one()
    lock.expires_at = datetime.utcnow() - timedelta(seconds=1)
    session.commit()
    session.expunge(lock)

    reclaimed = store.acquire_job_lock(
        job_name="daily_trading",
        market="a",
        trade_date=date(2026, 6, 6),
        lock_owner="worker-2",
    )

    assert reclaimed == job_key
    lock = session.execute(select(ScheduledJobLockRow)).scalar_one()
    assert lock.lock_owner == "worker-2"
    assert lock.status == "running"
    assert lock.finished_at is None


def test_run_status_update_cannot_cross_tenants(session=None):
    session = setup_db()
    from datetime import date as _date
    alice = PaperLedgerStore(session, TenantContext("alice"))
    bob = PaperLedgerStore(session, TenantContext("bob"))
    account = alice.get_or_create_account("a", "manual")
    run = alice.create_run(account.account_id, "a", _date.today(), "manual", {}, [])

    with pytest.raises(LookupError, match="paper run not found"):
        bob.update_run_status(run.run_id, "success")


def test_create_fill_requires_run_owned_by_tenant():
    session = setup_db()
    from datetime import date as _date
    alice = PaperLedgerStore(session, TenantContext("alice"))
    bob = PaperLedgerStore(session, TenantContext("bob"))
    account = alice.get_or_create_account("a", "manual")
    run = alice.create_run(account.account_id, "a", _date.today(), "manual", {}, [])

    with pytest.raises(LookupError, match="paper run not found"):
        bob.create_fill(run.run_id, account.account_id, "600519.SH", "BUY", 100, 10.0)


def test_create_run_rejects_cross_tenant_account():
    session = setup_db()
    from datetime import date as _date
    alice = PaperLedgerStore(session, TenantContext("alice"))
    bob = PaperLedgerStore(session, TenantContext("bob"))
    alice_account = alice.get_or_create_account("a", "manual")

    with pytest.raises(LookupError, match="paper account not found"):
        bob.create_run(
            account_id=alice_account.account_id,
            market="a",
            trade_date=_date.today(),
            run_source="manual",
            params={},
            watchlist=[],
        )


def test_create_fill_rejects_cross_tenant_account():
    session = setup_db()
    from datetime import date as _date
    alice = PaperLedgerStore(session, TenantContext("alice"))
    bob = PaperLedgerStore(session, TenantContext("bob"))
    alice_account = alice.get_or_create_account("a", "manual")
    alice_run = alice.create_run(
        account_id=alice_account.account_id, market="a", trade_date=_date.today(),
        run_source="manual", params={}, watchlist=[],
    )
    bob_account = bob.get_or_create_account("a", "manual")
    bob_run = bob.create_run(
        account_id=bob_account.account_id, market="a", trade_date=_date.today(),
        run_source="manual", params={}, watchlist=[],
    )

    with pytest.raises(LookupError, match="paper account not found"):
        bob.create_fill(bob_run.run_id, alice_account.account_id, "600519.SH", "BUY", 100, 10.0)


def test_create_nav_snapshot_rejects_cross_tenant_account():
    session = setup_db()
    from datetime import date as _date
    alice = PaperLedgerStore(session, TenantContext("alice"))
    bob = PaperLedgerStore(session, TenantContext("bob"))
    alice_account = alice.get_or_create_account("a", "manual")

    with pytest.raises(LookupError, match="paper account not found"):
        bob.create_nav_snapshot(
            account_id=alice_account.account_id,
            trade_date=_date.today(),
            nav=100.0,
            cash=50.0,
            positions_value=50.0,
            source="auto",
        )


def test_update_position_rejects_cross_tenant_account():
    session = setup_db()
    alice = PaperLedgerStore(session, TenantContext("alice"))
    bob = PaperLedgerStore(session, TenantContext("bob"))
    alice_account = alice.get_or_create_account("a", "manual")

    with pytest.raises(LookupError, match="paper account not found"):
        bob.update_position(
            account_id=alice_account.account_id,
            symbol="600519.SH",
            quantity=100,
            avg_cost=10.0,
        )
