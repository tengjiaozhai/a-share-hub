import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from src.paper_ledger.models import PaperBase
from src.paper_ledger.store import PaperLedgerStore
from src.storage.dependencies import get_runtime_store

logger = logging.getLogger(__name__)

CN_TZ = ZoneInfo("Asia/Shanghai")
DAILY_JOB_LOCK_TTL_SECONDS = 2 * 60 * 60


class DailyScheduler:
    """日频自动调度器"""

    def __init__(self):
        self._scheduler = AsyncIOScheduler(timezone=CN_TZ)
        self._setup_jobs()

    def _setup_jobs(self):
        """设置定时任务"""
        # A 股开盘前任务：周一至周五 9:15（北京时间）
        self._scheduler.add_job(
            self._run_a_share_job,
            CronTrigger(day_of_week="mon-fri", hour=9, minute=15, timezone=CN_TZ),
            id="a_share_daily",
            name="A股日频模拟交易",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )

        # 美股开盘前任务：周一至周五 21:15（北京时间）
        self._scheduler.add_job(
            self._run_us_job,
            CronTrigger(day_of_week="mon-fri", hour=21, minute=15, timezone=CN_TZ),
            id="us_daily",
            name="美股日频模拟交易",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )

    def start(self):
        """启动调度器"""
        if self._scheduler.running:
            logger.info("Daily scheduler already running")
            return
        self._scheduler.start()
        logger.info("Daily scheduler started")

    def stop(self):
        """停止调度器"""
        if not self._scheduler.running:
            return
        self._scheduler.shutdown()
        logger.info("Daily scheduler stopped")

    def next_run_at(self, market: str) -> str | None:
        """Return ISO timestamp of next scheduled run for the given market, or None."""
        job_id = "a_share_daily" if market == "a" else "us_daily"
        for job in self._scheduler.get_jobs():
            if job.id == job_id:
                return job.next_run_time.isoformat() if job.next_run_time else None
        return None

    def job_status(self, market: str) -> str:
        """Return 'active' if job exists and is scheduled, 'paused' if exists but no next_run, 'missing' otherwise."""
        job_id = "a_share_daily" if market == "a" else "us_daily"
        for job in self._scheduler.get_jobs():
            if job.id == job_id:
                return "active" if job.next_run_time else "paused"
        return "missing"

    def has_job(self, market: str) -> bool:
        """Return True if a job is registered for the given market."""
        return self.job_status(market) != "missing"

    async def _run_a_share_job(self):
        """运行 A 股日频任务"""
        await self._run_daily_job("a")

    async def _run_us_job(self):
        """运行美股日频任务"""
        await self._run_daily_job("us")

    async def _run_daily_job(self, market: str):
        """运行日频任务"""
        logger.info("Starting daily job for market: %s", market)
        run = None
        job_key = None
        store = None

        try:
            engine = get_runtime_store().engine
            # SQLite/local tests may not have Alembic applied. create_all is idempotent.
            PaperBase.metadata.create_all(engine)
            with Session(engine) as session:
                store = PaperLedgerStore(session)
                today = datetime.now(CN_TZ).date()
                job_key = store.acquire_job_lock(
                    job_name="daily_trading",
                    market=market,
                    trade_date=today,
                    ttl_seconds=DAILY_JOB_LOCK_TTL_SECONDS,
                )
                if job_key is None:
                    logger.info("Daily job lock already exists for market=%s date=%s", market, today)
                    return

                if store.check_run_exists(market, today, "auto"):
                    logger.info("Daily job for %s already has blocking run today", market)
                    store.finish_job_lock(job_key, "skipped", "blocking auto run already exists")
                    return

                account = store.get_or_create_account(market, "auto")
                run = store.create_run(
                    account_id=account.account_id,
                    market=market,
                    trade_date=today,
                    run_source="auto",
                    params={},
                    watchlist=[],
                )

                await self._execute_daily_trading(store, account.account_id, run.run_id, market)

                store.update_run_status(run.run_id, "success")
                store.finish_job_lock(job_key, "success")
                logger.info("Daily job for %s completed successfully", market)

        except Exception as e:
            logger.exception("Daily job for %s failed", market)
            if store is not None:
                if run is not None:
                    store.update_run_status(run.run_id, "failed", str(e))
                if job_key is not None:
                    store.finish_job_lock(job_key, "failed", str(e))

    async def _execute_daily_trading(self, store: PaperLedgerStore, account_id: str, run_id: str, market: str):
        """执行日频交易。

        真实交易编排尚未接入前，必须显式失败，不能把空实现标记为 success。
        """
        raise NotImplementedError("daily trading execution is not implemented")


# 全局调度器实例
_scheduler: DailyScheduler | None = None


def get_scheduler() -> DailyScheduler:
    """获取全局调度器"""
    global _scheduler
    if _scheduler is None:
        _scheduler = DailyScheduler()
    return _scheduler
