from datetime import date, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, Date
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class PaperBase(DeclarativeBase):
    pass


class PaperAccountRow(PaperBase):
    """纸面账户，按 market + account_kind 唯一"""
    __tablename__ = "paper_accounts"
    
    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False)  # "a" 或 "us"
    account_kind: Mapped[str] = mapped_column(String(16), nullable=False)  # "auto" 或 "manual"
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PaperRunRow(PaperBase):
    """每次运行一条记录"""
    __tablename__ = "paper_runs"
    
    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    run_source: Mapped[str] = mapped_column(String(16), nullable=False)  # "auto", "manual", "backfill"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")  # "running", "success", "failed"
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    watchlist_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PaperPositionRow(PaperBase):
    """当前持仓"""
    __tablename__ = "paper_positions"
    
    position_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PaperFillRow(PaperBase):
    """模拟成交明细"""
    __tablename__ = "paper_fills"
    
    fill_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # "BUY" 或 "SELL"
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)  # 成交价按前收盘价
    notional: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PaperNavDailyRow(PaperBase):
    """每日净值快照"""
    __tablename__ = "paper_nav_daily"
    
    nav_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    positions_value: Mapped[float] = mapped_column(Float, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="auto")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
