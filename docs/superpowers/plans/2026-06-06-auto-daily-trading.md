# 自动日频模拟交易与连续收益工作台 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前"手动点一次跑一次"的模拟交易，改成"按市场自动日频运行 + 手动沙盒试跑并存"的单一路径设计

**Architecture:** 
- 新建日频纸面账本作为业绩唯一权威
- A 股和美股各自独立账户、独立交易日历、独立收益曲线
- 自动任务内置在 FastAPI 进程中，单实例运行
- 手动试跑只写沙盒账户，不影响自动业绩

**Tech Stack:** FastAPI, SQLAlchemy, APScheduler, PostgreSQL

---

## Task 1: 新增纸面账本数据模型

**Files:**
- Modify: `src/storage/models.py`
- Create: `src/paper_ledger/models.py`
- Create: `tests/test_paper_ledger_models.py`

- [ ] **Step 1: 创建纸面账本模型文件**

```python
# src/paper_ledger/models.py
from datetime import datetime, date
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, Date
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class PaperAccountRow(Base):
    """纸面账户，按 market + account_kind 唯一"""
    __tablename__ = "paper_accounts"
    
    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    market: Mapped[str] = mapped_column(String(16), nullable=False)  # "a" 或 "us"
    account_kind: Mapped[str] = mapped_column(String(16), nullable=False)  # "auto" 或 "manual"
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PaperRunRow(Base):
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


class PaperPositionRow(Base):
    """当前持仓"""
    __tablename__ = "paper_positions"
    
    position_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PaperFillRow(Base):
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


class PaperNavDailyRow(Base):
    """每日净值快照"""
    __tablename__ = "paper_nav_daily"
    
    nav_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    positions_value: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

- [ ] **Step 2: 创建 __init__.py**

```python
# src/paper_ledger/__init__.py
from src.paper_ledger.models import (
    PaperAccountRow,
    PaperRunRow,
    PaperPositionRow,
    PaperFillRow,
    PaperNavDailyRow,
)

__all__ = [
    "PaperAccountRow",
    "PaperRunRow",
    "PaperPositionRow",
    "PaperFillRow",
    "PaperNavDailyRow",
]
```

- [ ] **Step 3: 编写测试**

```python
# tests/test_paper_ledger_models.py
from datetime import date, datetime
from src.paper_ledger.models import (
    PaperAccountRow,
    PaperRunRow,
    PaperPositionRow,
    PaperFillRow,
    PaperNavDailyRow,
)


def test_paper_account_row_creation():
    account = PaperAccountRow(
        account_id="acc-001",
        market="a",
        account_kind="auto",
        initial_capital=1000000.0,
    )
    assert account.account_id == "acc-001"
    assert account.market == "a"
    assert account.account_kind == "auto"
    assert account.initial_capital == 1000000.0


def test_paper_run_row_creation():
    run = PaperRunRow(
        run_id="run-001",
        account_id="acc-001",
        market="a",
        trade_date=date(2026, 6, 6),
        run_source="auto",
        status="success",
    )
    assert run.run_id == "run-001"
    assert run.status == "success"
    assert run.run_source == "auto"


def test_paper_fill_row_creation():
    fill = PaperFillRow(
        fill_id="fill-001",
        run_id="run-001",
        account_id="acc-001",
        symbol="600519.SH",
        action="BUY",
        quantity=100,
        price=1800.0,
        notional=180000.0,
    )
    assert fill.symbol == "600519.SH"
    assert fill.action == "BUY"
    assert fill.quantity == 100


def test_paper_nav_daily_row_creation():
    nav = PaperNavDailyRow(
        nav_id="nav-001",
        account_id="acc-001",
        trade_date=date(2026, 6, 6),
        nav=1020000.0,
        cash=500000.0,
        positions_value=520000.0,
    )
    assert nav.nav == 1020000.0
    assert nav.cash == 500000.0
```

- [ ] **Step 4: 运行测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_paper_ledger_models.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/paper_ledger/ tests/test_paper_ledger_models.py
git commit -m "feat: add paper ledger data models"
```

---

## Task 2: 创建纸面账本 CRUD 操作

**Files:**
- Create: `src/paper_ledger/store.py`
- Create: `tests/test_paper_ledger_store.py`

- [ ] **Step 1: 创建 store 文件**

```python
# src/paper_ledger/store.py
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
```

- [ ] **Step 2: 编写测试**

```python
# tests/test_paper_ledger_store.py
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.paper_ledger.models import Base
from src.paper_ledger.store import PaperLedgerStore


def setup_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_get_or_create_account():
    session = setup_db()
    store = PaperLedgerStore(session)
    
    account = store.get_or_create_account("a", "auto", 1000000.0)
    assert account.market == "a"
    assert account.account_kind == "auto"
    assert account.initial_capital == 1000000.0
    
    # 再次获取应该返回同一个
    account2 = store.get_or_create_account("a", "auto")
    assert account2.account_id == account.account_id


def test_create_run():
    session = setup_db()
    store = PaperLedgerStore(session)
    
    account = store.get_or_create_account("a", "auto")
    run = store.create_run(
        account_id=account.account_id,
        market="a",
        trade_date=date(2026, 6, 6),
        run_source="auto",
        params={"capital": 1000000},
        watchlist=["600519.SH"],
    )
    assert run.status == "running"
    assert run.run_source == "auto"


def test_create_fill():
    session = setup_db()
    store = PaperLedgerStore(session)
    
    account = store.get_or_create_account("a", "auto")
    run = store.create_run(account.account_id, "a", date(2026, 6, 6), "auto", {}, [])
    fill = store.create_fill(run.run_id, account.account_id, "600519.SH", "BUY", 100, 1800.0)
    
    assert fill.symbol == "600519.SH"
    assert fill.notional == 180000.0


def test_update_position():
    session = setup_db()
    store = PaperLedgerStore(session)
    
    account = store.get_or_create_account("a", "auto")
    store.update_position(account.account_id, "600519.SH", 100, 1800.0)
    
    position = store.get_position(account.account_id, "600519.SH")
    assert position.quantity == 100
    assert position.avg_cost == 1800.0
    
    # 更新持仓
    store.update_position(account.account_id, "600519.SH", 200, 1850.0)
    position = store.get_position(account.account_id, "600519.SH")
    assert position.quantity == 200


def test_nav_history():
    session = setup_db()
    store = PaperLedgerStore(session)
    
    account = store.get_or_create_account("a", "auto")
    store.create_nav_snapshot(account.account_id, date(2026, 6, 6), 1020000.0, 500000.0, 520000.0)
    store.create_nav_snapshot(account.account_id, date(2026, 6, 7), 1030000.0, 480000.0, 550000.0)
    
    history = store.get_nav_history(account.account_id, 10)
    assert len(history) == 2
    assert history[0].nav == 1030000.0  # 按日期倒序


def test_check_run_exists():
    session = setup_db()
    store = PaperLedgerStore(session)
    
    account = store.get_or_create_account("a", "auto")
    assert not store.check_run_exists("a", date(2026, 6, 6), "auto")
    
    run = store.create_run(account.account_id, "a", date(2026, 6, 6), "auto", {}, [])
    store.update_run_status(run.run_id, "success")
    
    assert store.check_run_exists("a", date(2026, 6, 6), "auto")
```

- [ ] **Step 3: 运行测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_paper_ledger_store.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/paper_ledger/store.py tests/test_paper_ledger_store.py
git commit -m "feat: add paper ledger CRUD operations"
```

---

## Task 3: 创建自动调度器

**Files:**
- Create: `src/scheduler/daily_scheduler.py`
- Create: `tests/test_daily_scheduler.py`

- [ ] **Step 1: 创建调度器文件**

```python
# src/scheduler/daily_scheduler.py
import logging
from datetime import date, datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.paper_ledger.store import PaperLedgerStore
from src.storage.dependencies import get_runtime_store

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
```

- [ ] **Step 2: 编写测试**

```python
# tests/test_daily_scheduler.py
from unittest.mock import patch, MagicMock
from src.scheduler.daily_scheduler import DailyScheduler


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


@patch("src.scheduler.daily_scheduler.PaperLedgerStore")
def test_scheduler_checks_existing_run(mock_store_class):
    mock_store = MagicMock()
    mock_store.check_run_exists.return_value = True
    mock_store_class.return_value = mock_store
    
    scheduler = DailyScheduler()
    # 这里需要异步测试，暂时跳过实际执行
```

- [ ] **Step 3: 运行测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_daily_scheduler.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/scheduler/ tests/test_daily_scheduler.py
git commit -m "feat: add daily scheduler for auto trading"
```

---

## Task 4: 集成调度器到 FastAPI

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: 修改 main.py 集成调度器**

```python
# 在 build_app 函数中添加
from src.scheduler.daily_scheduler import get_scheduler

def build_app():
    app = FastAPI(title="A股自动交易系统")
    
    # ... 现有代码 ...
    
    # 启动调度器
    @app.on_event("startup")
    async def startup_event():
        scheduler = get_scheduler()
        scheduler.start()
    
    @app.on_event("shutdown")
    async def shutdown_event():
        scheduler = get_scheduler()
        scheduler.stop()
    
    return app
```

- [ ] **Step 2: 运行测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/ -k "scheduler" -v
```

- [ ] **Step 3: 提交**

```bash
git add src/main.py
git commit -m "feat: integrate scheduler into FastAPI"
```

---

## Task 5: 扩展 Workbench API

**Files:**
- Modify: `src/api/routes_dashboard.py`

- [ ] **Step 1: 添加 automation 和 performance 字段**

```python
# 在 _build_workbench_payload 函数中添加
def _build_workbench_payload(store) -> dict:
    # ... 现有代码 ...
    
    # 获取纸面账本数据
    from src.paper_ledger.store import PaperLedgerStore
    from src.storage.db import get_engine
    from sqlalchemy.orm import Session
    
    engine = get_engine()
    with Session(engine) as session:
        ledger_store = PaperLedgerStore(session)
        
        # 获取 auto 账户
        a_account = ledger_store.get_or_create_account("a", "auto")
        us_account = ledger_store.get_or_create_account("us", "auto")
        
        # 获取净值历史
        a_nav_history = ledger_store.get_nav_history(a_account.account_id, 30)
        us_nav_history = ledger_store.get_nav_history(us_account.account_id, 30)
        
        # 构建 performance 数据
        performance = {
            "a_share": {
                "current_nav": a_nav_history[0].nav if a_nav_history else a_account.initial_capital,
                "daily_return": _calculate_daily_return(a_nav_history),
                "monthly_return": _calculate_period_return(a_nav_history, 30),
                "max_drawdown": _calculate_max_drawdown(a_nav_history),
                "nav_curve": [{"date": str(n.trade_date), "nav": n.nav} for n in reversed(a_nav_history)],
            },
            "us_stock": {
                "current_nav": us_nav_history[0].nav if us_nav_history else us_account.initial_capital,
                "daily_return": _calculate_daily_return(us_nav_history),
                "monthly_return": _calculate_period_return(us_nav_history, 30),
                "max_drawdown": _calculate_max_drawdown(us_nav_history),
                "nav_curve": [{"date": str(n.trade_date), "nav": n.nav} for n in reversed(us_nav_history)],
            },
        }
        
        # 构建 automation 数据
        from datetime import date
        today = date.today()
        automation = {
            "a_share": {
                "today_status": "completed" if ledger_store.check_run_exists("a", today, "auto") else "pending",
                "last_run": _get_last_run(ledger_store, "a"),
                "next_run_time": "09:15",
            },
            "us_stock": {
                "today_status": "completed" if ledger_store.check_run_exists("us", today, "auto") else "pending",
                "last_run": _get_last_run(ledger_store, "us"),
                "next_run_time": "21:15",
            },
        }
    
    payload["performance"] = performance
    payload["automation"] = automation
    
    return payload


def _calculate_daily_return(nav_history: list) -> float:
    if len(nav_history) < 2:
        return 0.0
    return (nav_history[0].nav - nav_history[1].nav) / nav_history[1].nav


def _calculate_period_return(nav_history: list, days: int) -> float:
    if len(nav_history) < 2:
        return 0.0
    return (nav_history[0].nav - nav_history[-1].nav) / nav_history[-1].nav


def _calculate_max_drawdown(nav_history: list) -> float:
    if not nav_history:
        return 0.0
    max_nav = nav_history[0].nav
    max_dd = 0.0
    for nav in reversed(nav_history):
        max_nav = max(max_nav, nav.nav)
        dd = (nav.nav - max_nav) / max_nav
        max_dd = min(max_dd, dd)
    return max_dd


def _get_last_run(ledger_store: PaperLedgerStore, market: str) -> dict | None:
    # TODO: 实现获取最后一次运行
    return None
```

- [ ] **Step 2: 运行测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py -v
```

- [ ] **Step 3: 提交**

```bash
git add src/api/routes_dashboard.py
git commit -m "feat: extend workbench API with automation and performance"
```

---

## Task 6: 更新前端展示

**Files:**
- Modify: `src/api/dashboard_page/partials/view_dashboard.html`
- Modify: `src/api/dashboard_page/scripts/dashboard.js`

- [ ] **Step 1: 添加今日自动运行状态**

```html
<!-- 在中间区域添加 -->
<div class="auto-status-card">
  <h3>今日自动运行状态</h3>
  <div class="status-grid">
    <div class="status-item">
      <span class="label">A 股</span>
      <span class="value" id="a-share-status">--</span>
    </div>
    <div class="status-item">
      <span class="label">美股</span>
      <span class="value" id="us-stock-status">--</span>
    </div>
  </div>
</div>
```

- [ ] **Step 2: 添加累计净值曲线**

```html
<!-- 在中间区域添加 -->
<div class="nav-curve-card">
  <h3>累计净值曲线</h3>
  <div id="nav-curve-chart" style="height: 200px;"></div>
</div>
```

- [ ] **Step 3: 添加右侧指标**

```html
<!-- 在右侧添加 -->
<div class="performance-card">
  <h3>今日收益</h3>
  <div class="value" id="daily-return">--</div>
</div>
<div class="performance-card">
  <h3>近30日收益</h3>
  <div class="value" id="monthly-return">--</div>
</div>
<div class="performance-card">
  <h3>近30日最大回撤</h3>
  <div class="value" id="max-drawdown">--</div>
</div>
<div class="performance-card">
  <h3>下次运行时间</h3>
  <div class="value" id="next-run-time">--</div>
</div>
```

- [ ] **Step 4: 添加区间表现对比**

```html
<!-- 在底部添加 -->
<div class="period-comparison-card">
  <h3>区间表现对比</h3>
  <div class="period-tabs">
    <button class="active" data-period="7d">7天</button>
    <button data-period="30d">30天</button>
    <button data-period="90d">90天</button>
    <button data-period="ytd">年初至今</button>
  </div>
  <div id="period-chart" style="height: 200px;"></div>
</div>
```

- [ ] **Step 5: 更新 JavaScript**

```javascript
// 在 dashboard.js 中添加
function updatePerformanceUI(performance) {
  if (!performance) return;
  
  const market = document.getElementById('cfg-market').value;
  const data = market === 'us' ? performance.us_stock : performance.a_share;
  
  document.getElementById('daily-return').textContent = formatPercent(data.daily_return);
  document.getElementById('monthly-return').textContent = formatPercent(data.monthly_return);
  document.getElementById('max-drawdown').textContent = formatPercent(data.max_drawdown);
  
  // 绘制净值曲线
  drawNavCurve(data.nav_curve);
}

function updateAutomationUI(automation) {
  if (!automation) return;
  
  const market = document.getElementById('cfg-market').value;
  const data = market === 'us' ? automation.us_stock : automation.a_share;
  
  document.getElementById('a-share-status').textContent = automation.a_share.today_status;
  document.getElementById('us-stock-status').textContent = automation.us_stock.today_status;
  document.getElementById('next-run-time').textContent = data.next_run_time;
}

function formatPercent(value) {
  return (value * 100).toFixed(2) + '%';
}

function drawNavCurve(curve) {
  // TODO: 使用图表库绘制曲线
  console.log('Drawing nav curve:', curve);
}
```

- [ ] **Step 6: 运行测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py -v
```

- [ ] **Step 7: 提交**

```bash
git add src/api/dashboard_page/ src/api/dashboard_page/scripts/dashboard.js
git commit -m "feat: update dashboard UI for auto trading"
```

---

## Task 7: 添加 Backfill 功能

**Files:**
- Create: `src/paper_ledger/backfill.py`
- Create: `tests/test_backfill.py`

- [ ] **Step 1: 创建 backfill 文件**

```python
# src/paper_ledger/backfill.py
import logging
from datetime import date, timedelta

from src.paper_ledger.store import PaperLedgerStore

logger = logging.getLogger(__name__)


async def backfill_recent_days(store: PaperLedgerStore, market: str, days: int = 30):
    """补算最近 N 个交易日的净值"""
    logger.info(f"Starting backfill for {market}, {days} days")
    
    account = store.get_or_create_account(market, "auto")
    today = date.today()
    
    for i in range(days, 0, -1):
        trade_date = today - timedelta(days=i)
        
        # 检查是否已存在
        if store.check_run_exists(market, trade_date, "backfill"):
            continue
        
        # 创建运行记录
        run = store.create_run(
            account_id=account.account_id,
            market=market,
            trade_date=trade_date,
            run_source="backfill",
            params={"backfill_days": days},
            watchlist=[],
        )
        
        try:
            # TODO: 执行实际的交易逻辑
            # 这里应该复用 _execute_daily_trading 的逻辑
            
            # 更新运行状态
            store.update_run_status(run.run_id, "success")
            
            logger.info(f"Backfill completed for {trade_date}")
        
        except Exception as e:
            logger.error(f"Backfill failed for {trade_date}: {e}")
            store.update_run_status(run.run_id, "failed", str(e))
    
    logger.info(f"Backfill completed for {market}")
```

- [ ] **Step 2: 编写测试**

```python
# tests/test_backfill.py
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.paper_ledger.models import Base
from src.paper_ledger.store import PaperLedgerStore
from src.paper_ledger.backfill import backfill_recent_days


def test_backfill_creates_runs():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    with Session(engine) as session:
        store = PaperLedgerStore(session)
        
        # 运行 backfill
        import asyncio
        asyncio.run(backfill_recent_days(store, "a", 5))
        
        # 验证创建了运行记录
        account = store.get_or_create_account("a", "auto")
        history = store.get_nav_history(account.account_id, 10)
        
        # 应该有一些记录
        assert len(history) > 0
```

- [ ] **Step 3: 运行测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_backfill.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/paper_ledger/backfill.py tests/test_backfill.py
git commit -m "feat: add backfill functionality"
```

---

## Task 8: 集成到启动流程

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: 添加 backfill 到启动流程**

```python
# 在 startup_event 中添加
@app.on_event("startup")
async def startup_event():
    scheduler = get_scheduler()
    scheduler.start()
    
    # 检查是否需要 backfill
    from src.paper_ledger.backfill import backfill_recent_days
    from src.paper_ledger.store import PaperLedgerStore
    from src.storage.db import get_engine
    from sqlalchemy.orm import Session
    
    engine = get_engine()
    with Session(engine) as session:
        store = PaperLedgerStore(session)
        
        # 检查 A 股账户
        a_account = store.get_or_create_account("a", "auto")
        a_history = store.get_nav_history(a_account.account_id, 1)
        if not a_history:
            await backfill_recent_days(store, "a", 30)
        
        # 检查美股账户
        us_account = store.get_or_create_account("us", "auto")
        us_history = store.get_nav_history(us_account.account_id, 1)
        if not us_history:
            await backfill_recent_days(store, "us", 30)
```

- [ ] **Step 2: 运行测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/ -k "backfill" -v
```

- [ ] **Step 3: 提交**

```bash
git add src/main.py
git commit -m "feat: add backfill to startup flow"
```

---

## Task 9: 运行完整测试

- [ ] **Step 1: 运行所有测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest -q
```

- [ ] **Step 2: 验证测试通过**

预期：所有测试通过

---

## Task 10: 更新文档

- [ ] **Step 1: 更新 README.md**

添加自动交易功能说明

- [ ] **Step 2: 更新 sop.md**

添加自动交易使用指南

- [ ] **Step 3: 提交**

```bash
git add README.md sop.md
git commit -m "docs: update documentation for auto trading"
```
