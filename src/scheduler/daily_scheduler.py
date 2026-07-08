import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from src.core.tenant import SYSTEM_TENANT
from src.market_calendar import get_trading_calendar
from src.market_calendar.service import TradingCalendarService
from src.paper_ledger.models import PaperBase
from src.paper_ledger.store import PaperLedgerStore
from src.storage.dependencies import get_runtime_engine

logger = logging.getLogger(__name__)

CN_TZ = ZoneInfo("Asia/Shanghai")
DAILY_JOB_LOCK_TTL_SECONDS = 2 * 60 * 60

# 默认自选股（按市场）
_DEFAULT_WATCHLIST: dict[str, list[str]] = {
    "a": [
        "600519.SH",   # 贵州茅台
        "000858.SZ",   # 五粮液
        "601318.SH",   # 中国平安
        "000333.SZ",   # 美的集团
        "600036.SH",   # 招商银行
    ],
    "us": [
        "AAPL.US",
        "MSFT.US",
        "NVDA.US",
        "GOOGL.US",
        "AMZN.US",
    ],
}

# 默认初始资金
_DEFAULT_CAPITAL = 1_000_000.0


class DailyScheduler:
    """日频自动调度器"""

    def __init__(self, calendar: TradingCalendarService | None = None):
        self._calendar = calendar or get_trading_calendar()
        self._scheduler = AsyncIOScheduler(timezone=CN_TZ)
        self._setup_jobs()

    def _setup_jobs(self):
        """设置定时任务"""
        self._scheduler.add_job(
            self._run_a_share_job,
            CronTrigger(day_of_week="mon-fri", hour=9, minute=15, timezone=CN_TZ),
            id="a_share_daily",
            name="A股日频模拟交易",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
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
        job_id = "a_share_daily" if market == "a" else "us_daily"
        for job in self._scheduler.get_jobs():
            if job.id == job_id:
                return job.next_run_time.isoformat() if job.next_run_time else None
        return None

    def job_status(self, market: str) -> str:
        job_id = "a_share_daily" if market == "a" else "us_daily"
        for job in self._scheduler.get_jobs():
            if job.id == job_id:
                return "active" if job.next_run_time else "paused"
        return "missing"

    def has_job(self, market: str) -> bool:
        return self.job_status(market) != "missing"

    async def _run_a_share_job(self):
        await self._run_daily_job("a")

    async def _run_us_job(self):
        await self._run_daily_job("us")

    async def _run_daily_job(self, market: str):
        """运行日频任务（使用 SYSTEM_TENANT，自动任务全局归属 system 账户）"""
        logger.info("Starting daily job for market: %s", market)
        run = None
        job_key = None
        store = None

        try:
            engine = get_runtime_engine()
            PaperBase.metadata.create_all(engine)
            with Session(engine) as session:
                store = PaperLedgerStore(session, SYSTEM_TENANT)
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
                market_session = self._calendar.get_session(market, today)
                if not market_session.is_trading_day:
                    reason = market_session.reason or "market closed"
                    run = store.create_run(
                        account_id=account.account_id,
                        market=market,
                        trade_date=today,
                        run_source="auto",
                        params={"calendar_reason": reason},
                        watchlist=[],
                    )
                    store.update_run_status(run.run_id, "skipped", reason)
                    store.finish_job_lock(job_key, "skipped", reason)
                    logger.info("Daily job for %s skipped: %s", market, reason)
                    return

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
        """执行日频模拟交易：获取行情 → 计算信号 → 生成目标仓位 → 模拟成交 → 更新持仓 → 记录净值"""
        from src.core.config import Settings
        from src.strategy.strategy_config import StrategyConfig
        from src.strategy.signal_engine import build_signal
        from src.indicators.technical_indicators import compute_feature_row
        from src.data.providers.provider_chain import build_provider_chain_from_settings
        from src.portfolio.target_planner import build_target_positions

        settings = Settings()
        strategy_config = StrategyConfig.from_settings(settings)
        provider_chain = build_provider_chain_from_settings()

        # 1. 获取账户当前状态
        account = store.get_or_create_account(market, "auto")
        positions = store.get_all_positions(account_id)
        current_positions: dict[str, dict] = {}
        positions_value = 0.0
        for pos in positions:
            current_positions[pos.symbol] = {
                "quantity": pos.quantity,
                "avg_cost": pos.avg_cost,
            }
            # 尝试获取最新价格计算市值
            try:
                snap = provider_chain.get_realtime_quote(pos.symbol)
                price = float(snap.close) if snap else pos.avg_cost
            except Exception:
                price = pos.avg_cost
            positions_value += pos.quantity * price

        cash = account.initial_capital - positions_value
        # 如果有历史净值记录，用更精确的 cash
        nav_history = store.get_nav_history(account_id, days=1)
        if nav_history:
            latest_nav = nav_history[0]
            cash = float(latest_nav.cash)
            positions_value = float(latest_nav.positions_value)

        capital_base = cash + positions_value  # 当前总净值
        logger.info(
            "Account state: cash=%.2f, positions_value=%.2f, nav=%.2f, positions=%d",
            cash, positions_value, capital_base, len(current_positions),
        )

        # 2. 获取 watchlist（优先用 run 参数中的，否则用默认）
        watchlist = _DEFAULT_WATCHLIST.get(market, _DEFAULT_WATCHLIST["a"])
        # 也包含当前持仓中不在 watchlist 的标的（以便判断是否卖出）
        for symbol in current_positions:
            if symbol not in watchlist:
                watchlist.append(symbol)

        # 3. 对每个标的计算技术信号
        decisions: list[dict] = []
        price_by_symbol: dict[str, float] = {}

        for symbol in watchlist:
            try:
                # 获取实时价格
                snap = provider_chain.get_realtime_quote(symbol)
                if snap is None:
                    logger.warning("No quote for %s, skipping", symbol)
                    continue
                current_price = float(snap.close)
                price_by_symbol[symbol] = current_price

                # 获取历史数据计算技术指标（需要至少 60 根 K 线）
                from datetime import timedelta
                end_date = datetime.now(CN_TZ)
                start_date = end_date - timedelta(days=strategy_config.confirm_lookback_days)
                hist_df = provider_chain.get_history(symbol, start_date, end_date, freq="daily")

                if hist_df is not None and not hist_df.empty and len(hist_df) >= 60:
                    close_prices = hist_df["close"].astype(float).tolist()
                    volumes = hist_df["volume"].astype(float).tolist() if "volume" in hist_df.columns else None
                    features = compute_feature_row(close_prices, volumes)
                else:
                    logger.warning("Insufficient history for %s (%d bars), using neutral features", symbol, len(hist_df) if hist_df is not None else 0)
                    features = compute_feature_row([])  # 返回中性默认值

                # 生成交易信号
                signal = build_signal(symbol, features, strategy_config)
                action = signal["action"]
                confidence = int(min(max(abs(signal["technical_score"]) * 100, 0), 100))

                logger.info(
                    "Signal for %s: action=%s score=%.4f rsi=%.1f",
                    symbol, action, signal["technical_score"], signal["rsi_14"],
                )

                decisions.append({
                    "symbol": symbol,
                    "action": action,
                    "confidence": confidence,
                    "target_position_ratio": strategy_config.max_position_ratio / max(len(watchlist), 1) if action == "BUY" else 0.0,
                    "reason": f"technical_score={signal['technical_score']:.4f} rsi={signal['rsi_14']:.1f}",
                })

            except Exception as e:
                logger.warning("Failed to process signal for %s: %s", symbol, e)
                continue

        if not decisions:
            logger.info("No actionable signals for market=%s, skipping execution", market)
            return

        # 4. 计算目标仓位
        targets = build_target_positions(
            decisions=decisions,
            prices=price_by_symbol,
            capital_base=capital_base,
            max_position_ratio=strategy_config.max_position_ratio,
            lot_size_a=strategy_config.lot_size_a,
            lot_size_us=strategy_config.lot_size_us,
            current_positions=current_positions,
            market=market,
        )

        logger.info("Generated %d target positions for market=%s", len(targets), market)

        # 5. 模拟成交：更新持仓 & 记录成交
        for target in targets:
            symbol = target["symbol"]
            action = target["action"]
            quantity = target["quantity"]
            price = price_by_symbol.get(symbol, target["price"])

            if quantity <= 0:
                continue

            # 记录成交
            store.create_fill(
                run_id=run_id,
                account_id=account_id,
                symbol=symbol,
                action=action,
                quantity=quantity,
                price=price,
            )

            # 更新持仓
            current_pos = store.get_position(account_id, symbol)
            if action == "BUY":
                if current_pos:
                    total_cost = current_pos.avg_cost * current_pos.quantity + price * quantity
                    new_qty = current_pos.quantity + quantity
                    new_avg = total_cost / new_qty if new_qty > 0 else 0.0
                    store.update_position(account_id, symbol, new_qty, new_avg)
                else:
                    store.update_position(account_id, symbol, quantity, price)
            elif action == "SELL":
                if current_pos:
                    sell_qty = min(quantity, current_pos.quantity)
                    new_qty = current_pos.quantity - sell_qty
                    if new_qty <= 0:
                        store.update_position(account_id, symbol, 0, 0.0)
                    else:
                        store.update_position(account_id, symbol, new_qty, current_pos.avg_cost)

            logger.info("Fill: %s %s %d @ %.2f", action, symbol, quantity, price)

        # 6. 计算最终净值并记录快照
        final_positions = store.get_all_positions(account_id)
        final_positions_value = 0.0
        for pos in final_positions:
            price = price_by_symbol.get(pos.symbol, pos.avg_cost)
            final_positions_value += pos.quantity * price

        # 重新计算 cash（初始资金 - 所有买入成本 + 所有卖出收入）
        # 简化：用 NAV 变化来追踪
        final_cash = cash
        for target in targets:
            if target["quantity"] <= 0:
                continue
            price = price_by_symbol.get(target["symbol"], target["price"])
            notional = target["quantity"] * price
            if target["action"] == "BUY":
                final_cash -= notional
            elif target["action"] == "SELL":
                final_cash += notional

        final_nav = final_cash + final_positions_value
        trade_date = datetime.now(CN_TZ).date()

        store.create_nav_snapshot(
            account_id=account_id,
            trade_date=trade_date,
            nav=final_nav,
            cash=final_cash,
            positions_value=final_positions_value,
            run_id=run_id,
            source="auto",
        )

        logger.info(
            "Daily trading completed: market=%s nav=%.2f cash=%.2f positions_value=%.2f fills=%d",
            market, final_nav, final_cash, final_positions_value, len(targets),
        )


_scheduler: DailyScheduler | None = None


def get_scheduler() -> DailyScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = DailyScheduler()
    return _scheduler
