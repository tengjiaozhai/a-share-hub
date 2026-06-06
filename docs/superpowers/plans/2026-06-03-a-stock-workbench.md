# A 股工作台实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- []`) syntax for tracking.

**Goal:** 将"实时行情"tab 重构为 A 股专用工作台，采用三栏布局，支持行情列表、K 线图、基本面数据。

**Architecture:** 新增 `src/a_stock/` 模块，包含自选列表 CRUD、K 线接口、基本面接口。重写 `view_market.html` 和 `market.js` 为三栏布局。复用腾讯行情 API。

**Tech Stack:** Python 3.11, FastAPI, psycopg, Alembic, PostgreSQL

---

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/a_stock/__init__.py` | 创建 | 模块初始化 |
| `src/a_stock/models.py` | 创建 | Pydantic 数据模型 |
| `src/a_stock/watchlist.py` | 创建 | 自选列表 CRUD |
| `src/a_stock/routes.py` | 创建 | FastAPI 路由 |
| `src/main.py` | 修改 | 注册 A 股路由 |
| `alembic/versions/20260603_000007_add_a_share_watchlist.py` | 创建 | 自选列表表 migration |
| `scripts/init_a_share_watchlist.py` | 创建 | 初始数据导入脚本 |
| `src/api/dashboard_page/partials/view_market.html` | 重写 | 三栏布局 |
| `src/api/dashboard_page/scripts/market.js` | 重写 | 完整交互逻辑 |
| `tests/a_stock/__init__.py` | 创建 | 测试包 |
| `tests/a_stock/test_routes.py` | 创建 | API 路由测试 |
| `tests/a_stock/test_watchlist.py` | 创建 | 自选列表测试 |

---

### Task 1: 创建数据库 Migration

**Files:**
- Create: `alembic/versions/20260603_000007_add_a_share_watchlist.py`

- [ ] **Step 1: 创建 migration 文件**

```python
from alembic import op
import sqlalchemy as sa


revision = "20260603_000007"
down_revision = "20260602_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "a_share_watchlist",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=20), nullable=False, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_a_share_watchlist_symbol", "a_share_watchlist", ["symbol"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_a_share_watchlist_symbol", table_name="a_share_watchlist")
    op.drop_table("a_share_watchlist")
```

- [ ] **Step 2: 运行 migration**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head
```

- [ ] **Step 3: 提交**

```bash
git add alembic/versions/20260603_000007_add_a_share_watchlist.py
git commit -m "db: add a_share_watchlist table migration"
```

---

### Task 2: 创建数据模型和自选列表 CRUD

**Files:**
- Create: `src/a_stock/__init__.py`
- Create: `src/a_stock/models.py`
- Create: `src/a_stock/watchlist.py`
- Create: `tests/a_stock/__init__.py`
- Create: `tests/a_stock/test_watchlist.py`

- [ ] **Step 1: 创建模块 __init__.py**

```python
```

- [ ] **Step 2: 创建 models.py**

```python
from datetime import datetime

from pydantic import BaseModel


class AStockWatchlistItem(BaseModel):
    id: int = 0
    symbol: str
    name: str
    sort_order: int = 0
    created_at: datetime | None = None


class AStockKline(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class AStockFundamental(BaseModel):
    symbol: str
    name: str = ""
    pe_ratio: float = 0.0
    turnover: float = 0.0
    amplitude: float = 0.0
    volume_ratio: float = 0.0
    market_cap: float = 0.0
    high_52w: float = 0.0
    low_52w: float = 0.0
```

- [ ] **Step 3: 创建 watchlist.py**

```python
import logging
from typing import Any

from src.a_stock.models import AStockWatchlistItem

logger = logging.getLogger(__name__)


class AShareWatchlistStore:
    """A 股自选列表 CRUD。"""

    def __init__(self, conn: Any):
        self._conn = conn

    def list_items(self) -> list[AStockWatchlistItem]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, symbol, name, sort_order, created_at FROM a_share_watchlist ORDER BY sort_order, id"
            )
            rows = cur.fetchall()
        return [
            AStockWatchlistItem(
                id=row["id"],
                symbol=row["symbol"],
                name=row["name"],
                sort_order=row["sort_order"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def add(self, symbol: str, name: str, sort_order: int = 0) -> AStockWatchlistItem:
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO a_share_watchlist (symbol, name, sort_order) VALUES (%s, %s, %s) "
                    "RETURNING id, symbol, name, sort_order, created_at",
                    (symbol.upper(), name, sort_order),
                )
                row = cur.fetchone()
                self._conn.commit()
        except Exception as e:
            self._conn.rollback()
            if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                raise ValueError(f"Symbol {symbol} already exists in watchlist") from e
            raise

        return AStockWatchlistItem(
            id=row["id"],
            symbol=row["symbol"],
            name=row["name"],
            sort_order=row["sort_order"],
            created_at=row["created_at"],
        )

    def remove(self, symbol: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM a_share_watchlist WHERE symbol = %s", (symbol.upper(),))
            deleted = cur.rowcount > 0
            self._conn.commit()
        return deleted

    def get_by_symbol(self, symbol: str) -> AStockWatchlistItem | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, symbol, name, sort_order, created_at FROM a_share_watchlist WHERE symbol = %s",
                (symbol.upper(),),
            )
            row = cur.fetchone()
        if not row:
            return None
        return AStockWatchlistItem(
            id=row["id"],
            symbol=row["symbol"],
            name=row["name"],
            sort_order=row["sort_order"],
            created_at=row["created_at"],
        )
```

- [ ] **Step 4: 创建测试**

```python
import pytest
from unittest.mock import MagicMock

from src.a_stock.watchlist import AShareWatchlistStore


@pytest.fixture
def mock_db():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def test_list_items(mock_db):
    conn, cursor = mock_db
    cursor.fetchall.return_value = [
        {"id": 1, "symbol": "600519.SH", "name": "贵州茅台", "sort_order": 0, "created_at": "2026-01-01"},
    ]
    store = AShareWatchlistStore(conn)
    items = store.list_items()
    assert len(items) == 1
    assert items[0].symbol == "600519.SH"


def test_add_item(mock_db):
    conn, cursor = mock_db
    cursor.fetchone.return_value = {
        "id": 1, "symbol": "600519.SH", "name": "贵州茅台", "sort_order": 0, "created_at": "2026-01-01",
    }
    store = AShareWatchlistStore(conn)
    item = store.add("600519.SH", "贵州茅台")
    assert item.symbol == "600519.SH"


def test_add_duplicate_raises(mock_db):
    conn, cursor = mock_db
    cursor.execute.side_effect = Exception("duplicate key")
    store = AShareWatchlistStore(conn)
    with pytest.raises(ValueError, match="already exists"):
        store.add("600519.SH", "贵州茅台")


def test_remove_item(mock_db):
    conn, cursor = mock_db
    cursor.rowcount = 1
    store = AShareWatchlistStore(conn)
    result = store.remove("600519.SH")
    assert result is True


def test_remove_not_found(mock_db):
    conn, cursor = mock_db
    cursor.rowcount = 0
    store = AShareWatchlistStore(conn)
    result = store.remove("INVALID")
    assert result is False
```

- [ ] **Step 5: 运行测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/a_stock/test_watchlist.py -v
```

- [ ] **Step 6: 提交**

```bash
git add src/a_stock/ tests/a_stock/
git commit -m "feat(a_stock): add models and watchlist CRUD with tests"
```

---

### Task 3: 创建 FastAPI 路由

**Files:**
- Create: `src/a_stock/routes.py`
- Modify: `src/main.py`
- Create: `tests/a_stock/test_routes.py`

- [ ] **Step 1: 创建 routes.py**

```python
import logging

from fastapi import APIRouter, HTTPException, Query

from src.a_stock.watchlist import AShareWatchlistStore
from src.data.providers.akshare_provider import AkshareProvider, _fetch_tencent_kline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/a-stock", tags=["a-stock"])

_watchlist_store: AShareWatchlistStore | None = None
_akshare_provider: AkshareProvider | None = None


def _get_watchlist_store() -> AShareWatchlistStore:
    global _watchlist_store
    if _watchlist_store is None:
        import psycopg
        from src.core.config import Settings
        settings = Settings()
        database_url = settings.database_url
        if not database_url:
            raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
        conn_url = database_url.replace("postgresql+psycopg://", "postgresql://")
        conn = psycopg.connect(conn_url, row_factory=psycopg.rows.dict_row)
        _watchlist_store = AShareWatchlistStore(conn)
    return _watchlist_store


def _get_akshare_provider() -> AkshareProvider:
    global _akshare_provider
    if _akshare_provider is None:
        _akshare_provider = AkshareProvider()
    return _akshare_provider


@router.get("/watchlist")
def list_watchlist() -> list[dict]:
    store = _get_watchlist_store()
    items = store.list_items()
    return [item.model_dump() for item in items]


@router.post("/watchlist")
def add_to_watchlist(body: dict) -> dict:
    symbol = body.get("symbol", "").strip().upper()
    name = body.get("name", "").strip()
    sort_order = int(body.get("sort_order", 0))
    if not symbol:
        raise HTTPException(status_code=422, detail="symbol is required")
    store = _get_watchlist_store()
    try:
        item = store.add(symbol, name or symbol, sort_order)
        return item.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/watchlist/{symbol}")
def remove_from_watchlist(symbol: str) -> dict:
    store = _get_watchlist_store()
    removed = store.remove(symbol.upper())
    if not removed:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found in watchlist")
    return {"removed": True, "symbol": symbol.upper()}


@router.post("/quotes")
def get_quotes(symbols: list[str]) -> list[dict]:
    """批量获取 A 股行情。"""
    from src.data.providers.akshare_provider import _fetch_tencent_quotes_batch
    if not symbols:
        return []
    df = _fetch_tencent_quotes_batch(symbols[:500])
    if df.empty:
        return []
    return df.to_dict("records")


@router.get("/kline/{symbol}")
def get_kline(
    symbol: str,
    period: str = Query("daily"),
    count: int = Query(60, ge=1, le=500),
) -> list[dict]:
    """获取 A 股 K 线数据。"""
    from datetime import datetime, timedelta

    normalized = symbol.strip().upper()
    provider = _get_akshare_provider()

    end_date = datetime.now()
    if period == "daily":
        start_date = end_date - timedelta(days=count * 2)
    elif period == "weekly":
        start_date = end_date - timedelta(days=count * 10)
    else:
        start_date = end_date - timedelta(days=count * 30)

    try:
        df = provider.get_history(normalized, start_date, end_date, freq=period)
    except Exception as e:
        logger.warning(f"get_kline({normalized}) failed: {e}")
        raise HTTPException(status_code=503, detail=f"K line data unavailable: {e}")

    if df.empty:
        return []

    records = df.tail(count).to_dict("records")
    return [
        {
            "date": str(r.get("date", "")),
            "open": float(r.get("open", 0)),
            "high": float(r.get("high", 0)),
            "low": float(r.get("low", 0)),
            "close": float(r.get("close", 0)),
            "volume": int(r.get("volume", 0)),
        }
        for r in records
    ]


@router.get("/fundamental/{symbol}")
def get_fundamental(symbol: str) -> dict:
    """获取 A 股基本面数据。"""
    from src.data.providers.akshare_provider import _fetch_tencent_quotes_batch

    normalized = symbol.strip().upper()
    df = _fetch_tencent_quotes_batch([normalized])

    if df.empty:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")

    row = df.iloc[0]
    return {
        "symbol": normalized,
        "name": str(row.get("name", "")),
        "pe_ratio": float(row.get("pe_ratio", 0) or 0),
        "turnover": float(row.get("turnover", 0) or 0),
        "amplitude": float(row.get("amplitude", 0) or 0),
        "volume_ratio": float(row.get("volume_ratio", 0) or 0),
        "market_cap": 0.0,
        "high_52w": 0.0,
        "low_52w": 0.0,
    }
```

- [ ] **Step 2: 修改 main.py 注册路由**

在 import 区域添加：
```python
from src.a_stock.routes import router as a_stock_router
```

在 `build_app()` 函数中添加：
```python
    app.include_router(a_stock_router)
```

- [ ] **Step 3: 创建测试**

```python
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.main import build_app


client = TestClient(build_app())


def test_get_watchlist():
    with patch("src.a_stock.routes._get_watchlist_store") as mock_store:
        mock_instance = MagicMock()
        mock_instance.list_items.return_value = []
        mock_store.return_value = mock_instance
        resp = client.get("/api/v1/a-stock/watchlist")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_add_watchlist_missing_symbol():
    resp = client.post("/api/v1/a-stock/watchlist", json={"name": "Test"})
    assert resp.status_code == 422


def test_get_kline():
    with patch("src.a_stock.routes._get_akshare_provider") as mock_prov:
        mock_instance = MagicMock()
        mock_instance.get_history.return_value = MagicMock(empty=True)
        mock_prov.return_value = mock_instance
        resp = client.get("/api/v1/a-stock/kline/600519.SH?period=daily&count=10")
    assert resp.status_code == 200
```

- [ ] **Step 4: 运行测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/a_stock/test_routes.py -v
```

- [ ] **Step 5: 运行 lint**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m ruff check src/a_stock/ src/main.py
```

- [ ] **Step 6: 提交**

```bash
git add src/a_stock/routes.py src/main.py tests/a_stock/test_routes.py
git commit -m "feat(a_stock): add FastAPI routes for watchlist, quotes, kline, fundamental"
```

---

### Task 4: 创建初始数据导入脚本

**Files:**
- Create: `scripts/init_a_share_watchlist.py`

- [ ] **Step 1: 创建脚本**

```python
"""导入 A 股热门股票到 a_share_watchlist 表。

用法:
    /opt/anaconda3/envs/py311/bin/python3 scripts/init_a_share_watchlist.py
"""

import os
import psycopg

HOT_STOCKS = [
    # 沪深300成分股（部分）
    ("600519.SH", "贵州茅台"), ("000858.SZ", "五粮液"), ("601318.SH", "中国平安"),
    ("000001.SZ", "平安银行"), ("600036.SH", "招商银行"), ("000333.SZ", "美的集团"),
    ("002594.SZ", "比亚迪"), ("601899.SH", "紫金矿业"), ("600900.SH", "长江电力"),
    ("600276.SH", "恒瑞医药"), ("000568.SZ", "泸州老窖"), ("002304.SZ", "洋河股份"),
    ("601398.SH", "工商银行"), ("601288.SH", "农业银行"), ("600030.SH", "中信证券"),
    ("601166.SH", "兴业银行"), ("000002.SZ", "万科A"), ("600000.SH", "浦发银行"),
    ("601012.SH", "隆基绿能"), ("600887.SH", "伊利股份"), ("000651.SZ", "格力电器"),
    ("002415.SZ", "海康威视"), ("600031.SH", "三一重工"), ("601088.SH", "中国神华"),
    ("600585.SH", "海螺水泥"), ("002475.SZ", "立讯精密"), ("300750.SZ", "宁德时代"),
    ("600809.SH", "山西汾酒"), ("002714.SZ", "牧原股份"), ("600050.SH", "中国联通"),
    ("601668.SH", "中国建筑"), ("600048.SH", "保利发展"), ("002352.SZ", "顺丰控股"),
    ("600104.SH", "上汽集团"), ("601857.SH", "中国石油"), ("600028.SH", "中国石化"),
    ("601390.SH", "中国中铁"), ("601669.SH", "中国电建"), ("002230.SZ", "科大讯飞"),
    ("300059.SZ", "东方财富"), ("002049.SZ", "紫光国微"), ("600745.SH", "闻泰科技"),
    ("002456.SZ", "欧菲光"), ("300433.SZ", "蓝思科技"), ("002241.SZ", "歌尔股份"),
    ("600588.SH", "用友网络"), ("002236.SZ", "大华股份"), ("300124.SZ", "汇川技术"),
    ("600570.SH", "恒生电子"), ("002230.SZ", "科大讯飞"), ("300015.SZ", "爱尔眼科"),
]


def main():
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn_url = database_url.replace("postgresql+psycopg://", "postgresql://")
    conn = psycopg.connect(conn_url, row_factory=psycopg.rows.dict_row)
    inserted = 0
    skipped = 0

    for i, (symbol, name) in enumerate(HOT_STOCKS):
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO a_share_watchlist (symbol, name, sort_order) VALUES (%s, %s, %s) "
                    "ON CONFLICT (symbol) DO NOTHING",
                    (symbol, name, i),
                )
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
        except Exception as e:
            print(f"Error inserting {symbol}: {e}")
            conn.rollback()

    conn.commit()
    conn.close()
    print(f"Done: inserted={inserted}, skipped={skipped}, total={len(HOT_STOCKS)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 运行脚本**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 scripts/init_a_share_watchlist.py
```

- [ ] **Step 3: 提交**

```bash
git add scripts/init_a_share_watchlist.py
git commit -m "feat(a_stock): add initial watchlist import script"
```

---

### Task 5: 重写 view_market.html — 三栏布局

**Files:**
- Modify: `src/api/dashboard_page/partials/view_market.html`

- [ ] **Step 1: 重写 view_market.html**

```html
<div class="view" id="view-market">
<div class="main">

  <!-- ── LEFT: 搜索 + 自选管理 ── -->
  <div class="panel-left">
    <h2>A 股工作台</h2>

    <div class="field">
      <label>搜索 A 股</label>
      <div style="display:flex;gap:6px">
        <input type="text" id="a-search-input" placeholder="输入代码或名称..." style="flex:1">
        <button class="us-btn-primary" onclick="aSearch()">搜索</button>
      </div>
      <div id="a-search-results" style="display:none;margin-top:6px;max-height:150px;overflow-y:auto"></div>
    </div>

    <div class="field">
      <label>自选管理</label>
      <div style="display:flex;gap:6px;margin-bottom:6px">
        <input type="text" id="a-add-symbol" placeholder="股票代码" style="flex:1">
        <button class="us-btn-add" onclick="aAddManual()">+ 添加</button>
      </div>
      <div id="a-watchlist-chips" style="display:flex;flex-wrap:wrap;gap:4px;max-height:120px;overflow-y:auto"></div>
    </div>

    <div class="field">
      <label>市场状态</label>
      <div id="a-market-status" style="font-size:12px;color:var(--dim)">加载中...</div>
    </div>

    <div class="field">
      <label>数据刷新</label>
      <div style="display:flex;gap:6px;align-items:center">
        <span id="a-last-refresh" style="font-size:11px;color:var(--dim)">--</span>
        <button class="us-btn-refresh" onclick="aLoadQuotes()">刷新</button>
      </div>
    </div>
  </div>

  <!-- ── CENTER: 行情列表 ── -->
  <div class="panel-center">
    <div class="tabs">
      <button class="active" onclick="aSwitchCenterTab(this,'a-quotes-pane')">行情列表</button>
      <button onclick="aSwitchCenterTab(this,'a-kline-pane')">K线图</button>
      <button onclick="aSwitchCenterTab(this,'a-fundamental-pane')">基本面</button>
    </div>

    <div class="tab-pane active" id="a-quotes-pane">
      <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center">
        <input type="text" id="a-quotes-search" placeholder="搜索代码或名称..." style="flex:1">
        <span id="a-quotes-count" style="font-size:12px;color:var(--dim)"></span>
      </div>
      <div id="a-quotes-loading" style="color:var(--dim);padding:20px;text-align:center">加载中...</div>
      <table class="table" id="a-quotes-table" style="display:none">
        <thead>
          <tr>
            <th>代码</th><th>名称</th><th>最新价</th><th>涨跌额</th><th>涨跌幅</th>
            <th>开盘</th><th>最高</th><th>最低</th><th>成交量</th><th>换手率</th><th>操作</th>
          </tr>
        </thead>
        <tbody id="a-quotes-body"></tbody>
      </table>
      <div id="a-quotes-pagination" style="display:flex;justify-content:center;align-items:center;gap:8px;margin-top:12px;font-size:12px"></div>
    </div>

    <div class="tab-pane" id="a-kline-pane">
      <div style="display:flex;gap:6px;margin-bottom:8px;align-items:center">
        <span style="font-size:12px;color:var(--dim)">周期:</span>
        <button class="us-kline-btn active" onclick="aSetKlinePeriod(this,'daily')">日K</button>
        <button class="us-kline-btn" onclick="aSetKlinePeriod(this,'weekly')">周K</button>
        <button class="us-kline-btn" onclick="aSetKlinePeriod(this,'monthly')">月K</button>
        <span id="a-kline-symbol" style="margin-left:auto;font-size:12px;color:var(--dim)">--</span>
      </div>
      <div id="a-kline-chart" style="min-height:300px;color:var(--dim);text-align:center;padding:40px">点击股票代码查看K线</div>
    </div>

    <div class="tab-pane" id="a-fundamental-pane">
      <div id="a-fundamental-content" style="padding:20px;color:var(--dim);text-align:center">点击股票代码查看基本面</div>
    </div>
  </div>

  <!-- ── RIGHT: 股票详情 ── -->
  <div class="panel-right">
    <h3><i class="bi bi-info-circle"></i> 股票详情</h3>
    <div id="a-detail-summary" style="font-size:12px;color:var(--dim)">点击股票代码查看详情</div>
    <div id="a-detail-content" style="display:none"></div>

    <h3 style="margin-top:16px"><i class="bi bi-clock-history"></i> 最近搜索</h3>
    <div id="a-recent-searches" style="font-size:12px;color:var(--dim)">暂无</div>
  </div>

</div>
</div>
```

- [ ] **Step 2: 提交**

```bash
git add src/api/dashboard_page/partials/view_market.html
git commit -m "feat(a_stock): rework market tab to three-column A-share workbench"
```

---

### Task 6: 重写 market.js — 完整交互逻辑

**Files:**
- Modify: `src/api/dashboard_page/scripts/market.js`

- [ ] **Step 1: 重写 market.js**

```javascript
// ── A 股工作台 ──

var aCurrentSymbol = null;
var aCurrentPeriod = 'daily';
var aRecentSearches = [];
var aRefreshTimer = null;

// ── 行情分页状态 ──
var aQuotesAllData = [];
var aQuotesFilteredData = [];
var aQuotesPage = 1;
var aQuotesPageSize = 30;
var aQuotesSearchQuery = '';

// ── 初始化 ──

function marketInit() {
  aLoadQuotes();
  aUpdateMarketStatus();
  aLoadWatchlistChips();

  aRefreshTimer = setInterval(function() {
    aLoadQuotes();
  }, 60000);

  // 行情搜索框
  var quotesSearch = document.getElementById('a-quotes-search');
  if (quotesSearch) {
    quotesSearch.addEventListener('input', function() {
      aQuotesSearchQuery = this.value.trim().toLowerCase();
      aQuotesPage = 1;
      aFilterAndRenderQuotes();
    });
  }

  // 左栏搜索框
  var searchInput = document.getElementById('a-search-input');
  if (searchInput) {
    searchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') aSearch();
    });
  }
}

// ── Tab 切换 ──

function aSwitchCenterTab(btn, paneId) {
  btn.parentElement.querySelectorAll('button').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  document.querySelectorAll('#view-market .tab-pane').forEach(function(p) { p.classList.remove('active'); });
  document.getElementById(paneId).classList.add('active');
}

// ── 行情加载 ──

function aLoadQuotes() {
  var loading = document.getElementById('a-quotes-loading');

  fetch('/api/v1/a-stock/watchlist')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data || data.length === 0) {
        aQuotesAllData = [];
        aFilterAndRenderQuotes();
        return;
      }
      var symbols = data.map(function(item) { return item.symbol; });
      return fetch('/api/v1/a-stock/quotes', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(symbols),
      }).then(function(r) { return r.json(); });
    })
    .then(function(quotes) {
      var now = new Date();
      var el = document.getElementById('a-last-refresh');
      if (el) el.textContent = '更新于 ' + now.toLocaleTimeString();
      aQuotesAllData = quotes || [];
      aFilterAndRenderQuotes();
    })
    .catch(function() {
      if (loading) loading.textContent = '加载失败，请检查网络';
    });
}

function aFilterAndRenderQuotes() {
  var loading = document.getElementById('a-quotes-loading');
  var table = document.getElementById('a-quotes-table');
  var tbody = document.getElementById('a-quotes-body');
  var countEl = document.getElementById('a-quotes-count');
  var paginationEl = document.getElementById('a-quotes-pagination');

  if (aQuotesSearchQuery) {
    aQuotesFilteredData = aQuotesAllData.filter(function(q) {
      var sym = (q.symbol || '').toLowerCase();
      var name = (q.name || '').toLowerCase();
      return sym.indexOf(aQuotesSearchQuery) !== -1 || name.indexOf(aQuotesSearchQuery) !== -1;
    });
  } else {
    aQuotesFilteredData = aQuotesAllData.slice();
  }

  if (countEl) {
    countEl.textContent = aQuotesFilteredData.length + ' / ' + aQuotesAllData.length + ' 只';
  }

  if (!aQuotesFilteredData || aQuotesFilteredData.length === 0) {
    if (loading) loading.textContent = aQuotesSearchQuery ? '无匹配结果' : '暂无自选股票，请在左侧添加';
    if (loading) loading.style.display = '';
    if (table) table.style.display = 'none';
    if (paginationEl) paginationEl.innerHTML = '';
    return;
  }

  if (loading) loading.style.display = 'none';
  if (table) table.style.display = '';

  var totalPages = Math.ceil(aQuotesFilteredData.length / aQuotesPageSize);
  if (aQuotesPage > totalPages) aQuotesPage = totalPages;
  if (aQuotesPage < 1) aQuotesPage = 1;
  var startIdx = (aQuotesPage - 1) * aQuotesPageSize;
  var pageData = aQuotesFilteredData.slice(startIdx, startIdx + aQuotesPageSize);

  if (tbody) {
    tbody.innerHTML = pageData.map(function(q) {
      var pct = parseFloat(q.change_pct) || 0;
      var color = pct > 0 ? 'var(--green)' : pct < 0 ? 'var(--red)' : 'var(--dim)';
      var sign = pct > 0 ? '+' : '';
      var close = parseFloat(q.close) || 0;
      var prevClose = parseFloat(q.prev_close) || 0;
      var chg = prevClose ? (close - prevClose).toFixed(2) : '-';
      var vol = q.volume ? (parseInt(q.volume) / 10000).toFixed(0) + '万' : '-';
      return '<tr>' +
        '<td><a href="#" onclick="aSelectSymbol(\'' + q.symbol + '\');return false" style="font-weight:600">' + (q.symbol || '') + '</a></td>' +
        '<td>' + (q.name || '-') + '</td>' +
        '<td>' + (close ? close.toFixed(2) : '-') + '</td>' +
        '<td style="color:' + color + '">' + chg + '</td>' +
        '<td style="color:' + color + '">' + sign + pct.toFixed(2) + '%</td>' +
        '<td>' + (parseFloat(q.open) || 0).toFixed(2) + '</td>' +
        '<td>' + (parseFloat(q.high) || 0).toFixed(2) + '</td>' +
        '<td>' + (parseFloat(q.low) || 0).toFixed(2) + '</td>' +
        '<td>' + vol + '</td>' +
        '<td>' + (parseFloat(q.turnover) || 0).toFixed(2) + '%</td>' +
        '<td><button onclick="aRemoveWatchlist(\'' + q.symbol + '\')" style="color:var(--red);background:none;border:none;cursor:pointer;font-size:11px">删除</button></td>' +
        '</tr>';
    }).join('');
  }

  if (paginationEl) {
    if (totalPages <= 1) {
      paginationEl.innerHTML = '';
      return;
    }
    var html = '';
    html += '<button class="us-page-btn" onclick="aGoToPage(1)" ' + (aQuotesPage === 1 ? 'disabled' : '') + '>&laquo;</button>';
    html += '<button class="us-page-btn" onclick="aGoToPage(' + (aQuotesPage - 1) + ')" ' + (aQuotesPage === 1 ? 'disabled' : '') + '>&lsaquo;</button>';
    html += '<span style="color:var(--muted)">' + aQuotesPage + ' / ' + totalPages + '</span>';
    html += '<button class="us-page-btn" onclick="aGoToPage(' + (aQuotesPage + 1) + ')" ' + (aQuotesPage === totalPages ? 'disabled' : '') + '>&rsaquo;</button>';
    html += '<button class="us-page-btn" onclick="aGoToPage(' + totalPages + ')" ' + (aQuotesPage === totalPages ? 'disabled' : '') + '>&raquo;</button>';
    paginationEl.innerHTML = html;
  }
}

function aGoToPage(page) {
  aQuotesPage = page;
  aFilterAndRenderQuotes();
}

// ── 搜索 ──

function aSearch() {
  var q = document.getElementById('a-search-input').value.trim();
  if (!q) return;
  var resultsDiv = document.getElementById('a-search-results');
  if (resultsDiv) {
    resultsDiv.style.display = '';
    resultsDiv.innerHTML = '<span style="color:var(--dim)">搜索中...</span>';
  }

  fetch('/api/v1/market/stocks?query=' + encodeURIComponent(q) + '&limit=20')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!resultsDiv) return;
      if (!data || data.length === 0) {
        resultsDiv.innerHTML = '<span style="color:var(--dim)">无结果</span>';
        return;
      }
      resultsDiv.innerHTML = data.map(function(s) {
        return '<div style="padding:4px 6px;cursor:pointer;border-bottom:1px solid var(--border);font-size:12px" ' +
          'onclick="aSelectSearchResult(\'' + s.symbol + '\',\'' + (s.name || '').replace(/'/g, "\\'") + '\')">' +
          '<strong>' + s.symbol + '</strong> ' + (s.name || '') + '</div>';
      }).join('');
    })
    .catch(function() {
      if (resultsDiv) resultsDiv.innerHTML = '<span style="color:var(--red)">搜索失败</span>';
    });
}

function aSelectSearchResult(symbol, name) {
  document.getElementById('a-search-input').value = symbol;
  document.getElementById('a-search-results').style.display = 'none';
  aAddToWatchlist(symbol, name || symbol);
  aAddRecentSearch(symbol);
}

function aAddRecentSearch(symbol) {
  aRecentSearches = aRecentSearches.filter(function(s) { return s !== symbol; });
  aRecentSearches.unshift(symbol);
  if (aRecentSearches.length > 10) aRecentSearches = aRecentSearches.slice(0, 10);
  var el = document.getElementById('a-recent-searches');
  if (el) {
    el.innerHTML = aRecentSearches.map(function(s) {
      return '<span style="display:inline-block;padding:2px 6px;margin:2px;border:1px solid var(--border);border-radius:3px;cursor:pointer;font-size:11px" onclick="aSelectSymbol(\'' + s + '\')">' + s + '</span>';
    }).join('');
  }
}

// ── 自选管理 ──

function aAddManual() {
  var input = document.getElementById('a-add-symbol');
  var symbol = (input.value || '').trim().toUpperCase();
  if (!symbol) return;
  aAddToWatchlist(symbol, symbol);
  input.value = '';
}

function aAddToWatchlist(symbol, name) {
  fetch('/api/v1/a-stock/watchlist', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({symbol: symbol, name: name}),
  }).then(function(r) {
    if (r.ok) {
      aLoadQuotes();
      aLoadWatchlistChips();
    } else {
      r.json().then(function(d) { alert(d.detail || '添加失败'); });
    }
  });
}

function aRemoveWatchlist(symbol) {
  if (!confirm('确认从自选删除 ' + symbol + '？')) return;
  fetch('/api/v1/a-stock/watchlist/' + symbol, {method: 'DELETE'})
    .then(function(r) {
      if (r.ok) {
        aLoadQuotes();
        aLoadWatchlistChips();
      }
    });
}

function aLoadWatchlistChips() {
  fetch('/api/v1/a-stock/watchlist')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var el = document.getElementById('a-watchlist-chips');
      if (!el) return;
      if (!data || data.length === 0) {
        el.innerHTML = '<span style="font-size:11px;color:var(--dim)">暂无自选</span>';
        return;
      }
      el.innerHTML = data.map(function(item) {
        return '<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 6px;border:1px solid var(--border);border-radius:3px;font-size:11px">' +
          '<a href="#" onclick="aSelectSymbol(\'' + item.symbol + '\');return false" style="color:var(--text);text-decoration:none">' + item.symbol + '</a>' +
          '<span style="color:var(--red);cursor:pointer" onclick="aRemoveWatchlist(\'' + item.symbol + '\')">&times;</span>' +
          '</span>';
      }).join('');
    });
}

// ── 股票选择 ──

function aSelectSymbol(symbol) {
  aCurrentSymbol = symbol;
  document.getElementById('a-kline-symbol').textContent = symbol;

  var klineBtn = document.querySelector('#view-market .tabs button:nth-child(2)');
  if (klineBtn) aSwitchCenterTab(klineBtn, 'a-kline-pane');

  aLoadKline();
  aLoadFundamental();
  aLoadDetailSummary(symbol);
  aAddRecentSearch(symbol);
}

// ── K 线 ──

function aSetKlinePeriod(btn, period) {
  btn.parentElement.querySelectorAll('.us-kline-btn').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  aCurrentPeriod = period;
  aLoadKline();
}

function aLoadKline() {
  if (!aCurrentSymbol) return;
  var chartDiv = document.getElementById('a-kline-chart');
  if (chartDiv) chartDiv.innerHTML = '<span style="color:var(--dim)">加载中...</span>';

  fetch('/api/v1/a-stock/kline/' + aCurrentSymbol + '?period=' + aCurrentPeriod + '&count=60')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data || data.length === 0) {
        if (chartDiv) chartDiv.innerHTML = '<span style="color:var(--dim)">无K线数据</span>';
        return;
      }
      aRenderKlineTable(chartDiv, data);
    })
    .catch(function() {
      if (chartDiv) chartDiv.innerHTML = '<span style="color:var(--red)">加载失败</span>';
    });
}

function aRenderKlineTable(container, klines) {
  var rows = klines.slice(-30);
  var html = '<div style="font-size:11px;color:var(--dim);margin-bottom:4px">最近 ' + rows.length + ' 根K线（共 ' + klines.length + ' 根）</div>';
  html += '<div style="max-height:350px;overflow-y:auto"><table class="table"><thead><tr>';
  html += '<th>日期</th><th>开</th><th>高</th><th>低</th><th>收</th><th>涨跌</th><th>成交量</th>';
  html += '</tr></thead><tbody>';

  rows.forEach(function(k, i) {
    var chg = i > 0 ? (k.close - rows[i-1].close) : 0;
    var chgPct = i > 0 && rows[i-1].close > 0 ? (chg / rows[i-1].close * 100) : 0;
    var color = chg > 0 ? 'var(--green)' : chg < 0 ? 'var(--red)' : 'var(--dim)';
    var vol = k.volume ? (k.volume / 10000).toFixed(0) + '万' : '-';
    html += '<tr>';
    html += '<td>' + k.date + '</td>';
    html += '<td>' + k.open.toFixed(2) + '</td>';
    html += '<td>' + k.high.toFixed(2) + '</td>';
    html += '<td>' + k.low.toFixed(2) + '</td>';
    html += '<td style="font-weight:600">' + k.close.toFixed(2) + '</td>';
    html += '<td style="color:' + color + '">' + (chgPct > 0 ? '+' : '') + chgPct.toFixed(2) + '%</td>';
    html += '<td>' + vol + '</td>';
    html += '</tr>';
  });

  html += '</tbody></table></div>';
  if (container) container.innerHTML = html;
}

// ── 基本面 ──

function aLoadFundamental() {
  if (!aCurrentSymbol) return;
  var el = document.getElementById('a-fundamental-content');
  if (el) el.innerHTML = '<span style="color:var(--dim)">加载中...</span>';

  fetch('/api/v1/a-stock/fundamental/' + aCurrentSymbol)
    .then(function(r) { return r.json(); })
    .then(function(f) {
      if (!el) return;
      var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px">';
      html += aFundRow('股票代码', f.symbol || '-');
      html += aFundRow('名称', f.name || '-');
      html += aFundRow('市盈率 (PE)', f.pe_ratio ? f.pe_ratio.toFixed(2) : '-');
      html += aFundRow('换手率', f.turnover ? f.turnover.toFixed(2) + '%' : '-');
      html += aFundRow('振幅', f.amplitude ? f.amplitude.toFixed(2) + '%' : '-');
      html += aFundRow('量比', f.volume_ratio ? f.volume_ratio.toFixed(2) : '-');
      html += '</div>';
      el.innerHTML = html;
    })
    .catch(function() {
      if (el) el.innerHTML = '<span style="color:var(--red)">加载失败</span>';
    });
}

function aFundRow(label, value) {
  return '<div style="color:var(--dim)">' + label + '</div><div style="font-weight:500">' + value + '</div>';
}

// ── 详情摘要 ──

function aLoadDetailSummary(symbol) {
  var el = document.getElementById('a-detail-summary');
  var content = document.getElementById('a-detail-content');
  if (el) el.style.display = 'none';
  if (content) {
    content.style.display = '';
    content.innerHTML = '<span style="color:var(--dim)">加载中...</span>';
  }

  fetch('/api/v1/a-stock/fundamental/' + symbol)
    .then(function(r) { return r.json(); })
    .then(function(f) {
      if (!content) return;
      var html = '<div style="font-size:12px">';
      html += '<div style="font-size:16px;font-weight:700;margin-bottom:4px">' + (f.name || symbol) + '</div>';
      html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px">';
      html += '<div style="color:var(--dim)">代码</div><div>' + (f.symbol || '-') + '</div>';
      html += '<div style="color:var(--dim)">PE</div><div>' + (f.pe_ratio ? f.pe_ratio.toFixed(2) : '-') + '</div>';
      html += '<div style="color:var(--dim)">换手率</div><div>' + (f.turnover ? f.turnover.toFixed(2) + '%' : '-') + '</div>';
      html += '<div style="color:var(--dim)">振幅</div><div>' + (f.amplitude ? f.amplitude.toFixed(2) + '%' : '-') + '</div>';
      html += '<div style="color:var(--dim)">量比</div><div>' + (f.volume_ratio ? f.volume_ratio.toFixed(2) : '-') + '</div>';
      html += '</div>';
      html += '</div>';
      content.innerHTML = html;
    })
    .catch(function() {
      if (content) content.innerHTML = '<span style="color:var(--red)">加载失败</span>';
    });
}

// ── 市场状态 ──

function aUpdateMarketStatus() {
  var el = document.getElementById('a-market-status');
  if (!el) return;

  var now = new Date();
  var hour = now.getHours();
  var min = now.getMinutes();
  var day = now.getDay();
  var isWeekday = day >= 1 && day <= 5;
  var timeNum = hour * 100 + min;
  var isMarketHours = (timeNum >= 930 && timeNum <= 1130) || (timeNum >= 1300 && timeNum <= 1500);
  var isOpen = isWeekday && isMarketHours;

  if (isOpen) {
    el.innerHTML = '<span style="color:var(--green)">交易中</span> (9:30-11:30 / 13:00-15:00)';
  } else if (isWeekday) {
    el.innerHTML = '<span style="color:var(--dim)">已收盘</span> (下次开盘: 周一至周五 9:30)';
  } else {
    el.innerHTML = '<span style="color:var(--dim)">周末休市</span>';
  }
}
```

- [ ] **Step 2: 修改 bootstrap.js**

在 `src/api/dashboard_page/scripts/bootstrap.js` 中找到初始化函数，在合适位置添加 `marketInit()` 调用。先读取该文件了解结构，然后在 init 函数末尾添加 `marketInit();`。

- [ ] **Step 3: 提交**

```bash
git add src/api/dashboard_page/scripts/market.js src/api/dashboard_page/scripts/bootstrap.js
git commit -m "feat(a_stock): rework market JS with full A-share workbench interactions"
```

---

### Task 7: 全量验证

- [ ] **Step 1: 运行全部测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/a_stock/ -v
```

- [ ] **Step 2: 运行 lint**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m ruff check src/a_stock/ src/main.py
```

- [ ] **Step 3: 启动服务验证**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve
```

访问 `http://127.0.0.1:8000/dashboard`，切换"实时行情"tab，验证：
- 三栏布局正确显示
- 搜索功能正常
- 自选管理（添加/删除）正常
- 行情列表加载
- K 线数据加载
- 基本面数据加载
- 分页功能正常

- [ ] **Step 4: 提交最终状态**

```bash
git add -A
git commit -m "feat(a_stock): complete A-share workbench with three-column layout"
```
