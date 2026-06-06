import uuid
from datetime import date, datetime
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from src.paper_ledger.models import (
    PaperAccountRow,
    PaperRunRow,
    PaperPositionRow,
    PaperFillRow,
    PaperNavDailyRow,
)


class PaperLedgerStore:
    """纸面账本 CRUD 操作"""
    
    def __init__(self, session: Session):
        self._session = session
    
    def get_or_create_account(self, market: str, account_kind: str, initial_capital: float = 1000000.0) -> PaperAccountRow:
        """获取或创建账户"""
        stmt = select(PaperAccountRow).where(
            and_(
                PaperAccountRow.market == market,
                PaperAccountRow.account_kind == account_kind,
            )
        )
        account = self._session.execute(stmt).scalar_one_or_none()
        if account is None:
            account = PaperAccountRow(
                account_id=f"acc-{market}-{account_kind}",
                market=market,
                account_kind=account_kind,
                initial_capital=initial_capital,
            )
            self._session.add(account)
            self._session.commit()
        return account
    
    def create_run(self, account_id: str, market: str, trade_date: date, run_source: str, params: dict, watchlist: list) -> PaperRunRow:
        """创建运行记录"""
        run = PaperRunRow(
            run_id=f"run-{uuid.uuid4().hex[:12]}",
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
        stmt = select(PaperRunRow).where(PaperRunRow.run_id == run_id)
        run = self._session.execute(stmt).scalar_one()
        run.status = status
        run.error_message = error_message
        self._session.commit()
    
    def create_fill(self, run_id: str, account_id: str, symbol: str, action: str, quantity: int, price: float) -> PaperFillRow:
        """创建成交记录"""
        fill = PaperFillRow(
            fill_id=f"fill-{uuid.uuid4().hex[:12]}",
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
                PaperPositionRow.account_id == account_id,
                PaperPositionRow.symbol == symbol,
            )
        )
        return self._session.execute(stmt).scalar_one_or_none()
    
    def update_position(self, account_id: str, symbol: str, quantity: int, avg_cost: float):
        """更新持仓"""
        position = self.get_position(account_id, symbol)
        if position is None:
            position = PaperPositionRow(
                position_id=f"pos-{uuid.uuid4().hex[:12]}",
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
        stmt = select(PaperPositionRow).where(PaperPositionRow.account_id == account_id)
        return list(self._session.execute(stmt).scalars().all())
    
    def create_nav_snapshot(self, account_id: str, trade_date: date, nav: float, cash: float, positions_value: float) -> PaperNavDailyRow:
        """创建净值快照"""
        nav_row = PaperNavDailyRow(
            nav_id=f"nav-{uuid.uuid4().hex[:12]}",
            account_id=account_id,
            trade_date=trade_date,
            nav=nav,
            cash=cash,
            positions_value=positions_value,
        )
        self._session.add(nav_row)
        self._session.commit()
        return nav_row
    
    def get_nav_history(self, account_id: str, days: int = 30) -> list[PaperNavDailyRow]:
        """获取净值历史"""
        stmt = (
            select(PaperNavDailyRow)
            .where(PaperNavDailyRow.account_id == account_id)
            .order_by(PaperNavDailyRow.trade_date.desc())
            .limit(days)
        )
        return list(self._session.execute(stmt).scalars().all())
    
    def check_run_exists(self, market: str, trade_date: date, run_source: str) -> bool:
        """检查是否已存在运行"""
        stmt = select(PaperRunRow).where(
            and_(
                PaperRunRow.market == market,
                PaperRunRow.trade_date == trade_date,
                PaperRunRow.run_source == run_source,
                PaperRunRow.status == "success",
            )
        )
        return self._session.execute(stmt).scalar_one_or_none() is not None
