import logging
from datetime import date, datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.paper_ledger.store import PaperLedgerStore
from src.paper_ledger.models import PaperBase

logger = logging.getLogger(__name__)


class DailyScheduler:
    """日频自动调度器"""
    
    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._setup_jobs()
    
    def _setup_jobs(self):
        """设置定时任务"""
        # A 股开盘前任务：周一至周五 9:15
        self._scheduler.add_job(
            self._run_a_share_job,
            CronTrigger(day_of_week="mon-fri", hour=9, minute=15),
            id="a_share_daily",
            name="A股日频模拟交易",
        )
        
        # 美股开盘前任务：周一至周五 21:15 (北京时间)
        self._scheduler.add_job(
            self._run_us_job,
            CronTrigger(day_of_week="mon-fri", hour=21, minute=15),
            id="us_daily",
            name="美股日频模拟交易",
        )
    
    def start(self):
        """启动调度器"""
        self._scheduler.start()
        logger.info("Daily scheduler started")
    
    def stop(self):
        """停止调度器"""
        self._scheduler.shutdown()
        logger.info("Daily scheduler stopped")
    
    async def _run_a_share_job(self):
        """运行 A 股日频任务"""
        await self._run_daily_job("a")
    
    async def _run_us_job(self):
        """运行美股日频任务"""
        await self._run_daily_job("us")
    
    async def _run_daily_job(self, market: str):
        """运行日频任务"""
        logger.info(f"Starting daily job for market: {market}")
        
        try:
            # 获取数据库会话
            from src.storage.db import get_engine
            from sqlalchemy.orm import Session
            
            engine = get_engine()
            with Session(engine) as session:
                store = PaperLedgerStore(session)
                
                # 检查是否已运行
                today = date.today()
                if store.check_run_exists(market, today, "auto"):
                    logger.info(f"Daily job for {market} already completed today")
                    return
                
                # 获取或创建账户
                account = store.get_or_create_account(market, "auto")
                
                # 创建运行记录
                run = store.create_run(
                    account_id=account.account_id,
                    market=market,
                    trade_date=today,
                    run_source="auto",
                    params={},
                    watchlist=[],
                )
                
                # 执行决策和模拟交易
                await self._execute_daily_trading(store, account.account_id, run.run_id, market)
                
                # 更新运行状态
                store.update_run_status(run.run_id, "success")
                
                logger.info(f"Daily job for {market} completed successfully")
        
        except Exception as e:
            logger.error(f"Daily job for {market} failed: {e}")
            # 记录失败状态
            if 'run' in locals():
                store.update_run_status(run.run_id, "failed", str(e))
    
    async def _execute_daily_trading(self, store: PaperLedgerStore, account_id: str, run_id: str, market: str):
        """执行日频交易"""
        # TODO: 实现实际的交易逻辑
        # 1. 获取观察列表
        # 2. 获取行情数据
        # 3. 运行决策引擎
        # 4. 执行模拟交易
        # 5. 更新持仓和净值
        pass


# 全局调度器实例
_scheduler: DailyScheduler | None = None


def get_scheduler() -> DailyScheduler:
    """获取全局调度器"""
    global _scheduler
    if _scheduler is None:
        _scheduler = DailyScheduler()
    return _scheduler
