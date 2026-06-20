import os
import socket
import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.tenant import TenantContext
from src.paper_ledger.models import (
    PaperAccountRow,
    PaperFillRow,
    PaperNavDailyRow,
    PaperPositionRow,
    PaperRunRow,
    ScheduledJobLockRow,
)


class PaperLedgerStore:
    """纸面账本 CRUD 操作（按绑定租户隔离）"""

    def __init__(self, session: Session, tenant: TenantContext):
        self._session = session
        self._tenant = tenant

    @property
    def user_id(self) -> str:
        return self._tenant.user_id

    def get_or_create_account(
        self,
        market: str,
        account_kind: str,
        initial_capital: float = 1000000.0,
    ) -> PaperAccountRow:
        """获取或创建账户（按 user_id + market + account_kind 唯一）"""
        stmt = select(PaperAccountRow).where(
            and_(
                PaperAccountRow.user_id == self.user_id,
                PaperAccountRow.market == market,
                PaperAccountRow.account_kind == account_kind,
            )
        )
        account = self._session.execute(stmt).scalar_one_or_none()
        if account is None:
            account = PaperAccountRow(
                account_id=f"acc-{self.user_id}-{market}-{account_kind}",
                user_id=self.user_id,
                market=market,
                account_kind=account_kind,
                initial_capital=initial_capital,
            )
            self._session.add(account)
            try:
                self._session.commit()
            except IntegrityError:
                self._session.rollback()
                account = self._session.execute(stmt).scalar_one()
        return account

    def create_run(
        self,
        account_id: str,
        market: str,
        trade_date: date,
        run_source: str,
        params: dict,
        watchlist: list,
    ) -> PaperRunRow:
        """创建运行记录（account 必须属于当前租户）"""
        account = self._session.execute(
            select(PaperAccountRow).where(
                PaperAccountRow.account_id == account_id,
                PaperAccountRow.user_id == self.user_id,
            )
        ).scalar_one_or_none()
        if account is None:
            raise LookupError(f"paper account not found: {account_id}")
        run = PaperRunRow(
            run_id=f"run-{uuid.uuid4().hex[:12]}",
            user_id=self.user_id,
            account_id=account_id,
            market=market,
            trade_date=trade_date,
            run_source=run_source,
            status="running",
            params_json=str(params),
            watchlist_json=str(watchlist),
        )
        self._session.add(run)
        self._session.commit()
        return run

    def update_run_status(self, run_id: str, status: str, error_message: str | None = None):
        """更新运行状态"""
        stmt = select(PaperRunRow).where(
            PaperRunRow.run_id == run_id,
            PaperRunRow.user_id == self.user_id,
        )
        run = self._session.execute(stmt).scalar_one_or_none()
        if run is None:
            raise LookupError(f"paper run not found: {run_id}")
        run.status = status
        run.error_message = error_message
        self._session.commit()

    def create_fill(
        self,
        run_id: str,
        account_id: str,
        symbol: str,
        action: str,
        quantity: int,
        price: float,
    ) -> PaperFillRow:
        """创建成交记录"""
        run = self._session.execute(
            select(PaperRunRow).where(
                PaperRunRow.run_id == run_id,
                PaperRunRow.user_id == self.user_id,
            )
        ).scalar_one_or_none()
        if run is None:
            raise LookupError(f"paper run not found: {run_id}")
        account = self._session.execute(
            select(PaperAccountRow).where(
                PaperAccountRow.account_id == account_id,
                PaperAccountRow.user_id == self.user_id,
            )
        ).scalar_one_or_none()
        if account is None:
            raise LookupError(f"paper account not found: {account_id}")
        fill = PaperFillRow(
            fill_id=f"fill-{uuid.uuid4().hex[:12]}",
            user_id=self.user_id,
            run_id=run_id,
            account_id=account_id,
            symbol=symbol,
            action=action,
            quantity=quantity,
            price=price,
            notional=quantity * price,
        )
        self._session.add(fill)
        self._session.commit()
        return fill

    def get_position(self, account_id: str, symbol: str) -> PaperPositionRow | None:
        """获取持仓"""
        stmt = select(PaperPositionRow).where(
            and_(
                PaperPositionRow.user_id == self.user_id,
                PaperPositionRow.account_id == account_id,
                PaperPositionRow.symbol == symbol,
            )
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def update_position(
        self,
        account_id: str,
        symbol: str,
        quantity: int,
        avg_cost: float,
    ):
        """更新持仓（account 必须属于当前租户）"""
        account = self._session.execute(
            select(PaperAccountRow).where(
                PaperAccountRow.account_id == account_id,
                PaperAccountRow.user_id == self.user_id,
            )
        ).scalar_one_or_none()
        if account is None:
            raise LookupError(f"paper account not found: {account_id}")
        position = self.get_position(account_id, symbol)
        if position is None:
            position = PaperPositionRow(
                position_id=f"pos-{self.user_id}-{account_id}-{symbol}",
                user_id=self.user_id,
                account_id=account_id,
                symbol=symbol,
                quantity=quantity,
                avg_cost=avg_cost,
            )
            self._session.add(position)
        else:
            position.quantity = quantity
            position.avg_cost = avg_cost
            position.updated_at = datetime.utcnow()
        self._session.commit()

    def get_all_positions(self, account_id: str) -> list[PaperPositionRow]:
        """获取所有持仓"""
        stmt = select(PaperPositionRow).where(
            and_(
                PaperPositionRow.user_id == self.user_id,
                PaperPositionRow.account_id == account_id,
            )
        )
        return list(self._session.execute(stmt).scalars().all())

    def create_nav_snapshot(
        self,
        account_id: str,
        trade_date: date,
        nav: float,
        cash: float,
        positions_value: float,
        run_id: str | None = None,
        source: str = "auto",
    ) -> PaperNavDailyRow:
        """创建净值快照（account 必须属于当前租户）"""
        account = self._session.execute(
            select(PaperAccountRow).where(
                PaperAccountRow.account_id == account_id,
                PaperAccountRow.user_id == self.user_id,
            )
        ).scalar_one_or_none()
        if account is None:
            raise LookupError(f"paper account not found: {account_id}")
        nav_row = PaperNavDailyRow(
            nav_id=f"nav-{self.user_id}-{account_id}-{trade_date.isoformat()}-{source}",
            user_id=self.user_id,
            account_id=account_id,
            trade_date=trade_date,
            nav=nav,
            cash=cash,
            positions_value=positions_value,
            run_id=run_id,
            source=source,
        )
        self._session.add(nav_row)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            existing = self._session.execute(
                select(PaperNavDailyRow).where(
                    and_(
                        PaperNavDailyRow.user_id == self.user_id,
                        PaperNavDailyRow.account_id == account_id,
                        PaperNavDailyRow.trade_date == trade_date,
                        PaperNavDailyRow.source == source,
                    )
                )
            ).scalar_one()
            return existing
        return nav_row

    def get_nav_history(self, account_id: str, days: int = 30) -> list[PaperNavDailyRow]:
        """获取净值历史"""
        stmt = (
            select(PaperNavDailyRow)
            .where(
                and_(
                    PaperNavDailyRow.user_id == self.user_id,
                    PaperNavDailyRow.account_id == account_id,
                )
            )
            .order_by(PaperNavDailyRow.trade_date.desc())
            .limit(days)
        )
        return list(self._session.execute(stmt).scalars().all())

    def check_run_exists(
        self,
        market: str,
        trade_date: date,
        run_source: str,
        blocking_statuses: tuple[str, ...] = ("running", "success", "skipped"),
    ) -> bool:
        """检查是否已存在会阻止再次调度的运行。

        自动调度不能只检查 success：并发场景下，另一个进程可能已经创建 running run，
        此时继续创建新 run 会导致同一市场同一交易日重复执行。
        """
        stmt = select(PaperRunRow).where(
            and_(
                PaperRunRow.user_id == self.user_id,
                PaperRunRow.market == market,
                PaperRunRow.trade_date == trade_date,
                PaperRunRow.run_source == run_source,
                PaperRunRow.status.in_(blocking_statuses),
            )
        )
        return self._session.execute(stmt).scalar_one_or_none() is not None

    @staticmethod
    def _job_key(job_name: str, market: str, trade_date: date) -> str:
        return f"{job_name}:{market}:{trade_date.isoformat()}"

    @staticmethod
    def _default_lock_owner() -> str:
        return f"{socket.gethostname()}:{os.getpid()}"

    def acquire_job_lock(
        self,
        job_name: str,
        market: str,
        trade_date: date,
        ttl_seconds: int = 3600,
        lock_owner: str | None = None,
    ) -> str | None:
        """尝试获取全局调度锁，成功返回 job_key，失败返回 None。

        锁归属全局（不按 user_id 隔离），多 worker / 多实例互斥同一自动任务。
        """
        now = datetime.utcnow()
        job_key = self._job_key(job_name, market, trade_date)
        row = ScheduledJobLockRow(
            job_key=job_key,
            job_name=job_name,
            market=market,
            trade_date=trade_date,
            status="running",
            lock_owner=lock_owner or self._default_lock_owner(),
            locked_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        self._session.add(row)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            result = self._session.execute(
                update(ScheduledJobLockRow)
                .where(
                    and_(
                        ScheduledJobLockRow.job_key == job_key,
                        ScheduledJobLockRow.status == "running",
                        ScheduledJobLockRow.expires_at <= now,
                    )
                )
                .values(
                    lock_owner=lock_owner or self._default_lock_owner(),
                    locked_at=now,
                    expires_at=now + timedelta(seconds=ttl_seconds),
                    finished_at=None,
                    error_message=None,
                )
            )
            if result.rowcount:
                self._session.commit()
                return job_key
            self._session.rollback()
            return None
        return job_key

    def finish_job_lock(self, job_key: str, status: str, error_message: str | None = None) -> None:
        """标记调度锁完成。"""
        row = self._session.execute(
            select(ScheduledJobLockRow).where(ScheduledJobLockRow.job_key == job_key)
        ).scalar_one_or_none()
        if row is None:
            return
        row.status = status
        row.error_message = error_message
        row.finished_at = datetime.utcnow()
        self._session.commit()

    def get_latest_run(
        self,
        market: str,
        account_kind: str,
    ) -> PaperRunRow | None:
        """获取最近一次成功的运行"""
        account = self.get_or_create_account(market, account_kind)
        stmt = (
            select(PaperRunRow)
            .where(
                and_(
                    PaperRunRow.user_id == self.user_id,
                    PaperRunRow.account_id == account.account_id,
                    PaperRunRow.status == "success",
                )
            )
            .order_by(PaperRunRow.created_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def get_nav_range(
        self,
        account_id: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 100,
    ) -> list[PaperNavDailyRow]:
        """获取指定日期范围内的净值记录"""
        conditions = [
            PaperNavDailyRow.user_id == self.user_id,
            PaperNavDailyRow.account_id == account_id,
        ]
        if start_date is not None:
            conditions.append(PaperNavDailyRow.trade_date >= start_date)
        if end_date is not None:
            conditions.append(PaperNavDailyRow.trade_date <= end_date)
        stmt = (
            select(PaperNavDailyRow)
            .where(and_(*conditions))
            .order_by(PaperNavDailyRow.trade_date.asc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_comparison_windows(
        self,
        account_id: str,
        windows: list[str] | None = None,
    ) -> dict[str, float]:
        """计算各时间窗口的收益率"""
        if windows is None:
            windows = ["7d", "30d", "90d", "ytd"]
        today = date.today()
        result: dict[str, float] = {}
        latest_row = self._session.execute(
            select(PaperNavDailyRow)
            .where(
                and_(
                    PaperNavDailyRow.user_id == self.user_id,
                    PaperNavDailyRow.account_id == account_id,
                )
            )
            .order_by(PaperNavDailyRow.trade_date.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest_row is None:
            return dict.fromkeys(windows, 0.0)
        latest_nav = float(latest_row.nav)

        for window in windows:
            if window == "ytd":
                start = date(today.year, 1, 1)
            else:
                days = int(window.rstrip("d"))
                start = today - __import__("datetime").timedelta(days=days)
            row = self._session.execute(
                select(PaperNavDailyRow)
                .where(
                    and_(
                        PaperNavDailyRow.user_id == self.user_id,
                        PaperNavDailyRow.account_id == account_id,
                        PaperNavDailyRow.trade_date <= start,
                    )
                )
                .order_by(PaperNavDailyRow.trade_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row is not None and float(row.nav) > 0:
                result[window] = round((latest_nav - float(row.nav)) / float(row.nav), 6)
            else:
                result[window] = 0.0
        return result

    def get_run_history(
        self,
        market: str,
        source: str = "all",
        limit: int = 20,
    ) -> list[PaperRunRow]:
        """获取运行历史，可按 source 过滤"""
        conditions = [
            PaperRunRow.user_id == self.user_id,
            PaperRunRow.market == market,
        ]
        if source != "all":
            conditions.append(PaperRunRow.run_source == source)
        stmt = (
            select(PaperRunRow)
            .where(and_(*conditions))
            .order_by(PaperRunRow.created_at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())