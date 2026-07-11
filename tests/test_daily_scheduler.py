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
async def test_daily_trading_execution_with_mock_data(monkeypatch):
    """测试日频交易执行流程（使用 mock 数据）"""
    from unittest.mock import MagicMock, patch
    from src.paper_ledger.models import PaperFillRow, PaperPositionRow, PaperNavDailyRow
    
    engine = create_engine("sqlite:///:memory:", future=True)
    PaperBase.metadata.create_all(engine)

    monkeypatch.setattr(
        "src.scheduler.daily_scheduler.get_runtime_engine",
        lambda: engine,
    )

    # Mock 数据提供者
    mock_snapshot = MagicMock()
    mock_snapshot.close = 100.0
    
    mock_provider = MagicMock()
    mock_provider.get_realtime_quote.return_value = mock_snapshot
    
    # Mock 历史数据（至少 60 根 K 线）
    import pandas as pd
    mock_history = pd.DataFrame({
        'close': [100.0 + i * 0.1 for i in range(100)],
        'volume': [1000000] * 100,
    })
    mock_provider.get_history.return_value = mock_history

    with patch('src.scheduler.daily_scheduler.build_provider_chain_from_settings') as mock_build:
        mock_build.return_value = mock_provider
        
        scheduler = DailyScheduler(calendar=FakeCalendar(is_trading_day=True))
        await scheduler._run_daily_job("a")

    today = datetime.now(CN_TZ).date()
    with Session(engine) as session:
        run = session.execute(select(PaperRunRow)).scalar_one()
        lock = session.execute(select(ScheduledJobLockRow)).scalar_one()
        fills = session.execute(select(PaperFillRow)).scalars().all()
        positions = session.execute(select(PaperPositionRow)).scalars().all()
        nav_snapshots = session.execute(select(PaperNavDailyRow)).scalars().all()

    # 验证运行成功
    assert run.market == "a"
    assert run.run_source == "auto"
    assert run.status == "success"
    assert run.error_message is None
    
    # 验证锁已释放
    assert lock.status == "success"
    
    # 验证生成了成交记录
    assert len(fills) > 0
    
    # 验证更新了持仓
    assert len(positions) > 0
    
    # 验证记录了净值快照
    assert len(nav_snapshots) > 0
    assert nav_snapshots[0].trade_date == today
    assert nav_snapshots[0].nav > 0


@pytest.mark.asyncio
async def test_non_trading_day_creates_skipped_run_without_executing(monkeypatch):
    engine = create_engine("sqlite:///:memory:", future=True)
    PaperBase.metadata.create_all(engine)

    monkeypatch.setattr(
        "src.scheduler.daily_scheduler.get_runtime_engine",
        lambda: engine,
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

    monkeypatch.setattr(
        "src.scheduler.daily_scheduler.get_runtime_engine",
        lambda: engine,
    )

    today = datetime.now(CN_TZ).date()
    with Session(engine) as session:
        from src.core.tenant import SYSTEM_TENANT
        from src.paper_ledger.store import PaperLedgerStore

        store = PaperLedgerStore(session, SYSTEM_TENANT)
        account = store.get_or_create_account(market="a", account_kind="auto")
        run = store.create_run(
            account_id=account.account_id,
            market="a",
            trade_date=today,
            run_source="auto",
            params={},
            watchlist=[],
        )
        store.update_run_status(run.run_id, "skipped", "A股休市")

    scheduler = DailyScheduler(calendar=FakeCalendar(is_trading_day=False, reason="A股休市"))
    await scheduler._run_daily_job("a")

    with Session(engine) as session:
        runs = session.execute(select(PaperRunRow)).scalars().all()
        lock = session.execute(select(ScheduledJobLockRow)).scalar_one()

    assert len(runs) == 1
    assert lock.status == "skipped"
    assert lock.error_message == "blocking auto run already exists"
