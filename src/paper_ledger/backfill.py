import logging
from datetime import date, timedelta
import math

from src.paper_ledger.store import PaperLedgerStore
from src.paper_ledger.models import PaperBase

logger = logging.getLogger(__name__)


def backfill_recent_days(
    store: PaperLedgerStore,
    market: str,
    days: int = 30,
    daily_return: float = 0.001,
) -> int:
    """补算最近 N 个交易日的净值（仅生成占位曲线，不执行业务逻辑）。

    返回成功补算的交易日数量。如该日已存在 backfill 成功运行则跳过。
    """
    logger.info(f"Starting backfill for {market}, {days} days")
    account = store.get_or_create_account(market, "auto")
    today = date.today()
    initial_capital = float(account.initial_capital)

    completed = 0
    nav = initial_capital
    for i in range(days, 0, -1):
        trade_date = today - timedelta(days=i)

        if store.check_run_exists(market, trade_date, "backfill"):
            continue

        run = store.create_run(
            account_id=account.account_id,
            market=market,
            trade_date=trade_date,
            run_source="backfill",
            params={"backfill_days": days, "daily_return": daily_return},
            watchlist=[],
        )

        try:
            oscillation = math.sin(i * 0.5) * (daily_return * 0.3)
            day_return = daily_return + oscillation
            nav = nav * (1.0 + day_return)
            cash = nav * 0.5
            positions_value = nav - cash

            store.create_nav_snapshot(
                account_id=account.account_id,
                trade_date=trade_date,
                nav=round(nav, 2),
                cash=round(cash, 2),
                positions_value=round(positions_value, 2),
            )
            store.update_run_status(run.run_id, "success")
            completed += 1
        except Exception as e:
            logger.error(f"Backfill failed for {trade_date}: {e}")
            store.update_run_status(run.run_id, "failed", str(e))

    logger.info(f"Backfill completed for {market}, {completed} days")
    return completed


def needs_backfill(store: PaperLedgerStore, market: str) -> bool:
    """是否需要补算：账户无任何 backfill 成功运行"""
    try:
        from sqlalchemy import select, and_
        from src.paper_ledger.models import PaperRunRow

        stmt = (
            select(PaperRunRow.run_id)
            .where(
                and_(
                    PaperRunRow.market == market,
                    PaperRunRow.run_source == "backfill",
                    PaperRunRow.status == "success",
                )
            )
            .limit(1)
        )
        return store._session.execute(stmt).scalar_one_or_none() is None
    except Exception:
        return False
