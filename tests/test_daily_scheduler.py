from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.paper_ledger.models import PaperBase, PaperRunRow, ScheduledJobLockRow
from src.scheduler.daily_scheduler import CN_TZ, DailyScheduler


class FakeCalendar:
    def __init__(self, is_trading_day: bool = True, reason: str | None = None):
        self._is_trading_day = is_trading_day
        self._reason = reason

    def get_session(self, market, trade_date):
        return SimpleNamespace(
            market=market,
            trade_date=trade_date,
            is_trading_day=self._is_trading_day,
            reason=self._reason,
        )


def test_scheduler_initialization():
    scheduler = DailyScheduler()
    assert scheduler._scheduler is not None


def test_scheduler_has_a_share_job():
    scheduler = DailyScheduler()
    jobs = scheduler._scheduler.get_jobs()
    job_ids = [job.id for job in jobs]
    assert "a_share_daily" in job_ids


def test_scheduler_has_us_job():
    scheduler = DailyScheduler()
    jobs = scheduler._scheduler.get_jobs()
    job_ids = [job.id for job in jobs]
    assert "us_daily" in job_ids


def test_scheduler_jobs_have_timezone_and_runtime_guards():
    scheduler = DailyScheduler()
    jobs = {job.id: job for job in scheduler._scheduler.get_jobs()}

    for job_id in ("a_share_daily", "us_daily"):
        job = jobs[job_id]
        assert job.trigger.timezone == CN_TZ
        assert job.max_instances == 1
        assert job.coalesce is True
        assert job.misfire_grace_time == 300


@pytest.mark.asyncio
async def test_unimplemented_daily_trading_marks_run_and_lock_failed(monkeypatch):
    engine = create_engine("sqlite:///:memory:", future=True)
    PaperBase.metadata.create_all(engine)

    class FakeRuntimeStore:
        def __init__(self, engine):
            self.engine = engine

    monkeypatch.setattr(
        "src.scheduler.daily_scheduler.get_runtime_store",
        lambda: FakeRuntimeStore(engine),
    )

    scheduler = DailyScheduler(calendar=FakeCalendar(is_trading_day=True))
    await scheduler._run_daily_job("a")

    today = datetime.now(CN_TZ).date()
    with Session(engine) as session:
        run = session.execute(select(PaperRunRow)).scalar_one()
        lock = session.execute(select(ScheduledJobLockRow)).scalar_one()

    assert run.market == "a"
    assert run.run_source == "auto"
    assert run.status == "failed"
    assert "daily trading execution is not implemented" in (run.error_message or "")
    assert lock.job_name == "daily_trading"
    assert lock.market == "a"
    assert lock.trade_date == today
    assert lock.status == "failed"


@pytest.mark.asyncio
async def test_non_trading_day_creates_skipped_run_without_executing(monkeypatch):
    engine = create_engine("sqlite:///:memory:", future=True)
    PaperBase.metadata.create_all(engine)

    class FakeRuntimeStore:
        def __init__(self, engine):
            self.engine = engine

    monkeypatch.setattr(
        "src.scheduler.daily_scheduler.get_runtime_store",
        lambda: FakeRuntimeStore(engine),
    )

    scheduler = DailyScheduler(calendar=FakeCalendar(is_trading_day=False, reason="A股休市"))
    await scheduler._run_daily_job("a")

    with Session(engine) as session:
        run = session.execute(select(PaperRunRow)).scalar_one()
        lock = session.execute(select(ScheduledJobLockRow)).scalar_one()

    assert run.status == "skipped"
    assert run.error_message == "A股休市"
    assert lock.status == "skipped"
    assert lock.error_message == "A股休市"


@pytest.mark.asyncio
async def test_existing_skipped_run_blocks_duplicate_daily_job(monkeypatch):
    engine = create_engine("sqlite:///:memory:", future=True)
    PaperBase.metadata.create_all(engine)

    class FakeRuntimeStore:
        def __init__(self, engine):
            self.engine = engine

    monkeypatch.setattr(
        "src.scheduler.daily_scheduler.get_runtime_store",
        lambda: FakeRuntimeStore(engine),
    )

    today = datetime.now(CN_TZ).date()
    with Session(engine) as session:
        from src.paper_ledger.store import PaperLedgerStore

        store = PaperLedgerStore(session)
        account = store.get_or_create_account("a", "auto")
        run = store.create_run(account.account_id, "a", today, "auto", {}, [])
        store.update_run_status(run.run_id, "skipped", "A股休市")

    scheduler = DailyScheduler(calendar=FakeCalendar(is_trading_day=False, reason="A股休市"))
    await scheduler._run_daily_job("a")

    with Session(engine) as session:
        runs = session.execute(select(PaperRunRow)).scalars().all()
        lock = session.execute(select(ScheduledJobLockRow)).scalar_one()

    assert len(runs) == 1
    assert lock.status == "skipped"
    assert lock.error_message == "blocking auto run already exists"
