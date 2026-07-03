from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column



class PaperBase(DeclarativeBase):
    pass


class PaperAccountRow(PaperBase):
    """纸面账户，按 user_id + market + account_kind 唯一"""
    __tablename__ = "paper_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "market", "account_kind", name="uq_paper_accounts_user_market_kind"),
    )
    __table_comment__ = "纸面账户表，存储模拟交易账户信息，按用户、市场和账户类型唯一标识"

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="账户ID，格式为 'acct-{user_id}-{market}-{account_kind}'")
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="账户所属用户ID")
    market: Mapped[str] = mapped_column(String(16), nullable=False, comment="市场类型：'a'（A股）或 'us'（美股）")
    account_kind: Mapped[str] = mapped_column(String(16), nullable=False, comment="账户类型：'auto'（自动交易）或 'manual'（手动沙盒）")
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False, comment="初始资金（单位：元）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")


class PaperRunRow(PaperBase):
    """每次运行一条记录"""
    __tablename__ = "paper_runs"
    __table_comment__ = "模拟交易运行记录表，每次运行（自动/手动/回填）生成一条记录"
    __table_args__ = (
        Index('ix_paper_runs_user_market_created', 'user_id', 'market', 'created_at'),
        Index('ix_paper_runs_user_source_created', 'user_id', 'run_source', 'created_at'),
    )


    run_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="运行ID，格式为 'run-{uuid}'")
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="运行所属用户ID")
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="关联账户ID")
    market: Mapped[str] = mapped_column(String(16), nullable=False, comment="市场类型：'a' 或 'us'")
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, comment="交易日期")
    run_source: Mapped[str] = mapped_column(String(16), nullable=False, comment="运行来源：'auto'（自动调度）、'manual'（手动触发）、'backfill'（启动补算）")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running", comment="运行状态：'running'（运行中）、'success'（成功）、'failed'（失败）")
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", comment="运行参数JSON，包含watchlist、资金配置等")
    watchlist_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", comment="观察列表JSON，本次运行使用的股票代码列表")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息，运行失败时记录详细错误")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")


class PaperPositionRow(PaperBase):
    """当前持仓"""
    __tablename__ = "paper_positions"
    __table_comment__ = "模拟交易持仓表，存储当前持仓状态，每次运行后更新"

    position_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="持仓ID，格式为 'pos-{user_id}-{account_id}-{symbol}'")
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="持仓所属用户ID")
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="关联账户ID")
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, comment="股票代码，如 '600519.SH'、'AAPL'")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, comment="持仓数量（股）")
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False, comment="平均成本价")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, comment="最后更新时间")


class PaperFillRow(PaperBase):
    """模拟成交明细"""
    __tablename__ = "paper_fills"
    __table_comment__ = "模拟成交明细表，记录每次运行产生的成交记录"

    fill_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="成交ID，格式为 'fill-{uuid}'")
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="成交所属用户ID")
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="关联运行ID")
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="关联账户ID")
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, comment="股票代码")
    action: Mapped[str] = mapped_column(String(16), nullable=False, comment="交易方向：'BUY'（买入）或 'SELL'（卖出）")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, comment="成交数量（股）")
    price: Mapped[float] = mapped_column(Float, nullable=False, comment="成交价格（按前收盘价计算）")
    notional: Mapped[float] = mapped_column(Float, nullable=False, comment="成交金额（quantity × price）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")


class PaperNavDailyRow(PaperBase):
    """每日净值快照"""
    __tablename__ = "paper_nav_daily"
    __table_args__ = (
        UniqueConstraint("user_id", "account_id", "trade_date", "source", name="uq_paper_nav_daily_user_account_date_source"),
    )
    __table_comment__ = "每日净值快照表，记录每个交易日的净值，用于绘制净值曲线和计算区间收益"

    nav_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="净值ID，格式为 'nav-{user_id}-{account_id}-{trade_date}'")
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="净值所属用户ID")
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="关联账户ID")
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, comment="交易日期")
    nav: Mapped[float] = mapped_column(Float, nullable=False, comment="当日净值（nav = cash + positions_value）")
    cash: Mapped[float] = mapped_column(Float, nullable=False, comment="现金余额")
    positions_value: Mapped[float] = mapped_column(Float, nullable=False, comment="持仓市值（按最新价计算）")
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="关联运行ID，启动补算时可能为空")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="auto", comment="数据来源：'auto'（自动运行）、'manual'（手动运行）、'backfill'（补算）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")


class ScheduledJobLockRow(PaperBase):
    """调度任务锁，保证 auto/backfill 等自动任务在多进程场景下单语义执行。"""
    __tablename__ = "scheduled_job_locks"
    __table_comment__ = "调度任务锁表，用于防止多 worker 或多实例重复执行同一市场同一交易日的自动任务"

    job_key: Mapped[str] = mapped_column(String(128), primary_key=True, comment="锁主键：{job_name}:{market}:{trade_date}")
    job_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="任务名称，如 daily_trading 或 startup_backfill")
    market: Mapped[str] = mapped_column(String(16), nullable=False, comment="市场类型：'a' 或 'us'")
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, comment="任务对应日期")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running", comment="锁状态：running/success/failed/skipped")
    lock_owner: Mapped[str] = mapped_column(String(128), nullable=False, comment="持有者标识，通常是 hostname:pid")
    locked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, comment="加锁时间")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="锁过期时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="完成时间")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="失败原因")
