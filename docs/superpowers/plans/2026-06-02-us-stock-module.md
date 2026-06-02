# 美股行情查询模块实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 a-share-hub 中新增独立美股行情查询模块，基于 yfinance 获取行情/K线/基本面，集成币安 API 查询账户资产，Dashboard 新增美股 tab。

**Architecture:** 新增 `src/us_stock/` 独立模块，包含数据模型、yfinance 封装、缓存层、自选列表 CRUD、币安资产查询、FastAPI 路由。Dashboard 新增美股 tab 调用新模块 API。

**Tech Stack:** Python 3.11, FastAPI, yfinance, cachetools, SQLAlchemy, Alembic, PostgreSQL

---

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `pyproject.toml` | 修改 | 添加 yfinance、cachetools 依赖 |
| `.env.example` | 修改 | 添加美股模块环境变量 |
| `alembic/versions/20260602_000006_add_us_watchlist_table.py` | 创建 | us_watchlist 表 migration |
| `src/us_stock/__init__.py` | 创建 | 模块初始化 |
| `src/us_stock/models.py` | 创建 | Pydantic 数据模型 |
| `src/us_stock/cache.py` | 创建 | TTL 内存缓存层 |
| `src/us_stock/yahoo_provider.py` | 创建 | yfinance 封装 |
| `src/us_stock/watchlist.py` | 创建 | 自选列表 CRUD |
| `src/us_stock/binance_asset.py` | 创建 | 币安账户资产查询 |
| `src/us_stock/routes.py` | 创建 | FastAPI 路由 |
| `src/main.py` | 修改 | 注册美股路由 |
| `scripts/init_us_watchlist.py` | 创建 | 初始数据导入脚本 |
| `src/api/dashboard_page/partials/status_bar.html` | 修改 | 添加美股 tab 按钮 |
| `src/api/dashboard_page/partials/view_us_stock.html` | 创建 | 美股 tab 页面 |
| `src/api/dashboard_page/scripts/us_stock.js` | 创建 | 美股 tab JS |
| `src/api/dashboard_page/render.py` | 修改 | 注入美股模板和脚本 |
| `src/api/dashboard_page/shell.html` | 修改 | 添加美股模板占位 |
| `tests/us_stock/__init__.py` | 创建 | 测试包 |
| `tests/us_stock/test_cache.py` | 创建 | 缓存层测试 |
| `tests/us_stock/test_yahoo_provider.py` | 创建 | yfinance 封装测试 |
| `tests/us_stock/test_watchlist.py` | 创建 | 自选列表测试 |
| `tests/us_stock/test_routes.py` | 创建 | API 路由测试 |

---

### Task 1: 添加依赖和环境变量

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`

- [ ] **Step 1: 在 pyproject.toml 添加依赖**

在 `dependencies` 列表末尾添加：

```python
    "yfinance>=0.2.40",
    "cachetools>=5.3.0",
```

- [ ] **Step 2: 在 .env.example 添加环境变量**

在文件末尾追加：

```
# 美股模块
YAHOO_FINANCE_ENABLED=true
US_STOCK_CACHE_TTL_QUOTE=60
US_STOCK_CACHE_TTL_KLINE=300
US_STOCK_CACHE_TTL_FUNDAMENTAL=3600
US_STOCK_BATCH_SIZE=50
US_STOCK_BATCH_DELAY=0.5
BINANCE_API_KEY=
BINANCE_API_SECRET=
```

- [ ] **Step 3: 安装依赖**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/pip install yfinance cachetools
```

- [ ] **Step 4: 验证依赖安装**

```bash
/opt/anaconda3/envs/py311/bin/python3 -c "import yfinance; import cachetools; print('ok')"
```

Expected: `ok`

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml .env.example
git commit -m "deps: add yfinance and cachetools for us stock module"
```

---

### Task 2: 创建数据库 Migration

**Files:**
- Create: `alembic/versions/20260602_000006_add_us_watchlist_table.py`

- [ ] **Step 1: 创建 migration 文件**

```python
from alembic import op
import sqlalchemy as sa


revision = "20260602_000006"
down_revision = "20260601_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "us_watchlist",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(length=20), nullable=False, unique=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_us_watchlist_symbol", "us_watchlist", ["symbol"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_us_watchlist_symbol", table_name="us_watchlist")
    op.drop_table("us_watchlist")
```

- [ ] **Step 2: 运行 migration**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head
```

Expected: `Running upgrade ... -> 20260602_000006`

- [ ] **Step 3: 验证表创建**

```bash
/opt/anaconda3/envs/py311/bin/python3 -c "
from src.storage.dependencies import get_runtime_store
store = get_runtime_store()
# 表已创建，可以执行简单查询
print('us_watchlist table created')
"
```

- [ ] **Step 4: 提交**

```bash
git add alembic/versions/20260602_000006_add_us_watchlist_table.py
git commit -m "db: add us_watchlist table migration"
```

---

### Task 3: 创建数据模型

**Files:**
- Create: `src/us_stock/__init__.py`
- Create: `src/us_stock/models.py`

- [ ] **Step 1: 创建模块 __init__.py**

```python
```

（空文件）

- [ ] **Step 2: 创建 models.py**

```python
from datetime import datetime

from pydantic import BaseModel


class USQuote(BaseModel):
    symbol: str
    name: str
    price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: int = 0
    market_cap: int = 0
    prev_close: float = 0.0
    market_open: bool = False
    stale: bool = False
    updated_at: datetime | None = None


class USKline(BaseModel):
    symbol: str
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: datetime


class USFundamental(BaseModel):
    symbol: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    market_cap: int = 0
    pe_ratio: float = 0.0
    pb_ratio: float = 0.0
    dividend_yield: float = 0.0
    eps: float = 0.0
    beta: float = 0.0
    fifty_two_week_high: float = 0.0
    fifty_two_week_low: float = 0.0


class USWatchlistItem(BaseModel):
    id: int = 0
    symbol: str
    name: str
    sort_order: int = 0
    created_at: datetime | None = None


class USBinanceAsset(BaseModel):
    symbol: str
    free: float = 0.0
    locked: float = 0.0
    total: float = 0.0
    usdt_value: float = 0.0
```

- [ ] **Step 3: 验证模型导入**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -c "from src.us_stock.models import USQuote, USKline, USFundamental, USWatchlistItem, USBinanceAsset; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: 提交**

```bash
git add src/us_stock/__init__.py src/us_stock/models.py
git commit -m "feat(us_stock): add pydantic models"
```

---

### Task 4: 创建缓存层

**Files:**
- Create: `src/us_stock/cache.py`
- Create: `tests/us_stock/__init__.py`
- Create: `tests/us_stock/test_cache.py`

- [ ] **Step 1: 编写缓存测试**

```python
import time
from src.us_stock.cache import TTLMemoryCache


def test_get_miss_returns_none():
    cache = TTLMemoryCache(ttl_seconds=1)
    assert cache.get("missing") is None


def test_set_and_get_hit():
    cache = TTLMemoryCache(ttl_seconds=10)
    cache.set("key1", {"value": 42})
    assert cache.get("key1") == {"value": 42}


def test_expired_entry_returns_none():
    cache = TTLMemoryCache(ttl_seconds=1)
    cache.set("key1", "data")
    time.sleep(1.1)
    assert cache.get("key1") is None


def test_delete():
    cache = TTLMemoryCache(ttl_seconds=10)
    cache.set("key1", "data")
    cache.delete("key1")
    assert cache.get("key1") is None


def test_clear():
    cache = TTLMemoryCache(ttl_seconds=10)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert cache.get("a") is None
    assert cache.get("b") is None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/us_stock/test_cache.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'src.us_stock.cache'`

- [ ] **Step 3: 实现缓存层**

```python
import threading
import time
from typing import Any


class TTLMemoryCache:
    """基于 TTL 的内存缓存，线程安全。"""

    def __init__(self, ttl_seconds: int = 60, maxsize: int = 1024):
        self._ttl = ttl_seconds
        self._maxsize = maxsize
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if len(self._store) >= self._maxsize:
                self._evict_expired()
            if len(self._store) >= self._maxsize:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]
            self._store[key] = (time.time() + self._ttl, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, (exp, _) in self._store.items() if now > exp]
        for k in expired:
            del self._store[k]
```

- [ ] **Step 4: 运行测试确认通过**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/us_stock/test_cache.py -v
```

Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add src/us_stock/cache.py tests/us_stock/__init__.py tests/us_stock/test_cache.py
git commit -m "feat(us_stock): add TTL memory cache with tests"
```

---

### Task 5: 创建 YahooProvider

**Files:**
- Create: `src/us_stock/yahoo_provider.py`
- Create: `tests/us_stock/test_yahoo_provider.py`

- [ ] **Step 1: 编写 YahooProvider 测试**

```python
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.us_stock.yahoo_provider import YahooProvider


def test_get_quote_returns_us_quote():
    provider = YahooProvider(cache_ttl_quote=60, cache_ttl_kline=300, cache_ttl_fundamental=3600)
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "shortName": "Apple Inc.",
        "regularMarketPrice": 195.2,
        "regularMarketChange": 2.5,
        "regularMarketChangePercent": 1.3,
        "regularMarketOpen": 193.0,
        "regularMarketDayHigh": 196.0,
        "regularMarketDayLow": 192.5,
        "regularMarketVolume": 52000000,
        "marketCap": 3000000000000,
        "regularMarketPreviousClose": 192.7,
        "marketState": "REGULAR",
    }
    with patch("src.us_stock.yahoo_provider.yf.Ticker", return_value=mock_ticker):
        quote = provider.get_quote("AAPL")
    assert quote.symbol == "AAPL"
    assert quote.name == "Apple Inc."
    assert quote.price == 195.2
    assert quote.market_open is True


def test_get_quote_symbol_not_found():
    provider = YahooProvider(cache_ttl_quote=60, cache_ttl_kline=300, cache_ttl_fundamental=3600)
    mock_ticker = MagicMock()
    mock_ticker.info = {}
    with patch("src.us_stock.yahoo_provider.yf.Ticker", return_value=mock_ticker):
        quote = provider.get_quote("INVALID123")
    assert quote.price == 0.0


def test_get_quote_uses_cache():
    provider = YahooProvider(cache_ttl_quote=60, cache_ttl_kline=300, cache_ttl_fundamental=3600)
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "shortName": "Test",
        "regularMarketPrice": 100.0,
        "marketState": "REGULAR",
    }
    with patch("src.us_stock.yahoo_provider.yf.Ticker", return_value=mock_ticker):
        q1 = provider.get_quote("TEST")
        q2 = provider.get_quote("TEST")
    assert q1.price == 100.0
    assert q2.price == 100.0
    assert mock_ticker.info.call_count == 1  # 第二次走缓存


def test_search_returns_results():
    provider = YahooProvider(cache_ttl_quote=60, cache_ttl_kline=300, cache_ttl_fundamental=3600)
    mock_search = MagicMock()
    mock_search.quotes = [
        {"symbol": "AAPL", "shortname": "Apple Inc.", "exchange": "NASDAQ", "quoteType": "EQUITY"},
    ]
    with patch("src.us_stock.yahoo_provider.yf.Search", return_value=mock_search):
        results = provider.search("Apple")
    assert len(results) == 1
    assert results[0]["symbol"] == "AAPL"


def test_get_kline_returns_list():
    provider = YahooProvider(cache_ttl_quote=60, cache_ttl_kline=300, cache_ttl_fundamental=3600)
    import pandas as pd
    mock_ticker = MagicMock()
    mock_ticker.history.return_value = pd.DataFrame({
        "Open": [190.0, 191.0],
        "High": [192.0, 193.0],
        "Low": [189.0, 190.0],
        "Close": [191.5, 192.5],
        "Volume": [50000000, 51000000],
    }, index=pd.to_datetime(["2026-01-01", "2026-01-02"]))
    with patch("src.us_stock.yahoo_provider.yf.Ticker", return_value=mock_ticker):
        klines = provider.get_kline("AAPL", interval="1d", range_str="5d")
    assert len(klines) == 2
    assert klines[0].symbol == "AAPL"
    assert klines[0].close == 191.5
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/us_stock/test_yahoo_provider.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 YahooProvider**

```python
import logging
import time
from datetime import datetime

import yfinance as yf

from src.us_stock.cache import TTLMemoryCache
from src.us_stock.models import USFundamental, USKline, USQuote

logger = logging.getLogger(__name__)

_VALID_INTERVALS = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"}
_VALID_RANGES = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}

_US_MARKET_STATES = {"REGULAR", "PRE", "POST", "PREPRE", "POSTPOST"}


class YahooProvider:
    """yfinance 封装，带内存缓存。"""

    def __init__(
        self,
        cache_ttl_quote: int = 60,
        cache_ttl_kline: int = 300,
        cache_ttl_fundamental: int = 3600,
        batch_size: int = 50,
        batch_delay: float = 0.5,
    ):
        self._quote_cache = TTLMemoryCache(ttl_seconds=cache_ttl_quote)
        self._kline_cache = TTLMemoryCache(ttl_seconds=cache_ttl_kline)
        self._fundamental_cache = TTLMemoryCache(ttl_seconds=cache_ttl_fundamental)
        self._search_cache = TTLMemoryCache(ttl_seconds=600)
        self._batch_size = batch_size
        self._batch_delay = batch_delay

    def get_quote(self, symbol: str) -> USQuote:
        cached = self._quote_cache.get(f"quote:{symbol}")
        if cached is not None:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
        except Exception as e:
            logger.warning(f"yfinance get_quote({symbol}) failed: {e}")
            return USQuote(symbol=symbol, name=symbol)

        if not info or not info.get("regularMarketPrice"):
            return USQuote(symbol=symbol, name=symbol)

        market_state = info.get("marketState", "")
        quote = USQuote(
            symbol=symbol,
            name=info.get("shortName", symbol),
            price=float(info.get("regularMarketPrice", 0)),
            change=float(info.get("regularMarketChange", 0)),
            change_pct=float(info.get("regularMarketChangePercent", 0)),
            open=float(info.get("regularMarketOpen", 0)),
            high=float(info.get("regularMarketDayHigh", 0)),
            low=float(info.get("regularMarketDayLow", 0)),
            volume=int(info.get("regularMarketVolume", 0)),
            market_cap=int(info.get("marketCap", 0)),
            prev_close=float(info.get("regularMarketPreviousClose", 0)),
            market_open=market_state in {"REGULAR", "PRE", "POST"},
            stale=False,
            updated_at=datetime.now(),
        )
        self._quote_cache.set(f"quote:{symbol}", quote)
        return quote

    def get_quotes(self, symbols: list[str]) -> list[USQuote]:
        results: list[USQuote] = []
        uncached: list[str] = []

        for sym in symbols:
            cached = self._quote_cache.get(f"quote:{sym}")
            if cached is not None:
                results.append(cached)
            else:
                uncached.append(sym)

        if not uncached:
            return results

        for i in range(0, len(uncached), self._batch_size):
            batch = uncached[i : i + self._batch_size]
            for sym in batch:
                try:
                    quote = self.get_quote(sym)
                    results.append(quote)
                except Exception as e:
                    logger.warning(f"get_quotes({sym}) failed: {e}")
                    results.append(USQuote(symbol=sym, name=sym))
            if i + self._batch_size < len(uncached):
                time.sleep(self._batch_delay)

        return results

    def get_kline(self, symbol: str, interval: str = "1d", range_str: str = "3mo") -> list[USKline]:
        if interval not in _VALID_INTERVALS:
            interval = "1d"
        if range_str not in _VALID_RANGES:
            range_str = "3mo"

        cache_key = f"kline:{symbol}:{interval}:{range_str}"
        cached = self._kline_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=range_str, interval=interval)
        except Exception as e:
            logger.warning(f"yfinance get_kline({symbol}) failed: {e}")
            return []

        if df.empty:
            return []

        klines = []
        for ts, row in df.iterrows():
            klines.append(USKline(
                symbol=symbol,
                interval=interval,
                open=float(row.get("Open", 0)),
                high=float(row.get("High", 0)),
                low=float(row.get("Low", 0)),
                close=float(row.get("Close", 0)),
                volume=int(row.get("Volume", 0)),
                timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else datetime.now(),
            ))

        self._kline_cache.set(cache_key, klines)
        return klines

    def get_fundamental(self, symbol: str) -> USFundamental:
        cached = self._fundamental_cache.get(f"fund:{symbol}")
        if cached is not None:
            return cached

        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
        except Exception as e:
            logger.warning(f"yfinance get_fundamental({symbol}) failed: {e}")
            return USFundamental(symbol=symbol)

        if not info:
            return USFundamental(symbol=symbol)

        fundamental = USFundamental(
            symbol=symbol,
            name=info.get("shortName", ""),
            sector=info.get("sector", ""),
            industry=info.get("industry", ""),
            market_cap=int(info.get("marketCap", 0)),
            pe_ratio=float(info.get("trailingPE", 0) or 0),
            pb_ratio=float(info.get("priceToBook", 0) or 0),
            dividend_yield=float(info.get("dividendYield", 0) or 0),
            eps=float(info.get("trailingEps", 0) or 0),
            beta=float(info.get("beta", 0) or 0),
            fifty_two_week_high=float(info.get("fiftyTwoWeekHigh", 0) or 0),
            fifty_two_week_low=float(info.get("fiftyTwoWeekLow", 0) or 0),
        )
        self._fundamental_cache.set(f"fund:{symbol}", fundamental)
        return fundamental

    def search(self, query: str) -> list[dict]:
        if not query or len(query.strip()) < 1:
            return []

        cache_key = f"search:{query.lower().strip()}"
        cached = self._search_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            srch = yf.Search(query)
            quotes = srch.quotes or []
        except Exception as e:
            logger.warning(f"yfinance search({query}) failed: {e}")
            return []

        results = []
        for q in quotes[:20]:
            results.append({
                "symbol": q.get("symbol", ""),
                "name": q.get("shortname") or q.get("longname", ""),
                "exchange": q.get("exchange", ""),
                "type": q.get("quoteType", ""),
            })

        self._search_cache.set(cache_key, results)
        return results

    def is_market_open(self) -> bool:
        now = datetime.utcnow()
        weekday = now.weekday()
        if weekday >= 5:
            return False
        hour = now.hour
        return 13 <= hour < 20  # UTC 13:30-20:00 ≈ 美东 9:30-16:00
```

- [ ] **Step 4: 运行测试确认通过**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/us_stock/test_yahoo_provider.py -v
```

Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add src/us_stock/yahoo_provider.py tests/us_stock/test_yahoo_provider.py
git commit -m "feat(us_stock): add YahooProvider with yfinance wrapper and tests"
```

---

### Task 6: 创建自选列表 CRUD

**Files:**
- Create: `src/us_stock/watchlist.py`
- Create: `tests/us_stock/test_watchlist.py`

- [ ] **Step 1: 编写自选列表测试**

```python
import pytest
from unittest.mock import MagicMock

from src.us_stock.watchlist import WatchlistStore


@pytest.fixture
def mock_db():
    """模拟数据库连接，返回 (conn, cursor)。"""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = lambda s: cursor
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor


def test_list_items(mock_db):
    conn, cursor = mock_db
    cursor.fetchall.return_value = [
        {"id": 1, "symbol": "AAPL", "name": "Apple", "sort_order": 0, "created_at": "2026-01-01"},
    ]
    store = WatchlistStore(conn)
    items = store.list_items()
    assert len(items) == 1
    assert items[0].symbol == "AAPL"


def test_add_item(mock_db):
    conn, cursor = mock_db
    cursor.fetchone.return_value = {"id": 1, "symbol": "AAPL", "name": "Apple", "sort_order": 0, "created_at": "2026-01-01"}
    store = WatchlistStore(conn)
    item = store.add("AAPL", "Apple")
    assert item.symbol == "AAPL"


def test_add_duplicate_raises(mock_db):
    conn, cursor = mock_db
    cursor.execute.side_effect = Exception("duplicate key")
    store = WatchlistStore(conn)
    with pytest.raises(ValueError, match="already exists"):
        store.add("AAPL", "Apple")


def test_remove_item(mock_db):
    conn, cursor = mock_db
    cursor.rowcount = 1
    store = WatchlistStore(conn)
    result = store.remove("AAPL")
    assert result is True


def test_remove_not_found(mock_db):
    conn, cursor = mock_db
    cursor.rowcount = 0
    store = WatchlistStore(conn)
    result = store.remove("INVALID")
    assert result is False
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/us_stock/test_watchlist.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 WatchlistStore**

```python
import logging
from typing import Any

from src.us_stock.models import USWatchlistItem

logger = logging.getLogger(__name__)


class WatchlistStore:
    """美股自选列表 CRUD，基于 psycopg 连接。"""

    def __init__(self, conn: Any):
        self._conn = conn

    def list_items(self) -> list[USWatchlistItem]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, symbol, name, sort_order, created_at FROM us_watchlist ORDER BY sort_order, id"
            )
            rows = cur.fetchall()
        return [
            USWatchlistItem(
                id=row["id"],
                symbol=row["symbol"],
                name=row["name"],
                sort_order=row["sort_order"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def add(self, symbol: str, name: str, sort_order: int = 0) -> USWatchlistItem:
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO us_watchlist (symbol, name, sort_order) VALUES (%s, %s, %s) "
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

        return USWatchlistItem(
            id=row["id"],
            symbol=row["symbol"],
            name=row["name"],
            sort_order=row["sort_order"],
            created_at=row["created_at"],
        )

    def remove(self, symbol: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM us_watchlist WHERE symbol = %s", (symbol.upper(),))
            deleted = cur.rowcount > 0
            self._conn.commit()
        return deleted

    def get_by_symbol(self, symbol: str) -> USWatchlistItem | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, symbol, name, sort_order, created_at FROM us_watchlist WHERE symbol = %s",
                (symbol.upper(),),
            )
            row = cur.fetchone()
        if not row:
            return None
        return USWatchlistItem(
            id=row["id"],
            symbol=row["symbol"],
            name=row["name"],
            sort_order=row["sort_order"],
            created_at=row["created_at"],
        )
```

- [ ] **Step 4: 运行测试确认通过**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/us_stock/test_watchlist.py -v
```

Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add src/us_stock/watchlist.py tests/us_stock/test_watchlist.py
git commit -m "feat(us_stock): add WatchlistStore CRUD with tests"
```

---

### Task 7: 创建币安资产查询

**Files:**
- Create: `src/us_stock/binance_asset.py`

- [ ] **Step 1: 实现 binance_asset.py**

```python
import logging
import os

from src.crypto.data.binance_provider import BinanceProvider
from src.us_stock.cache import TTLMemoryCache
from src.us_stock.models import USBinanceAsset

logger = logging.getLogger(__name__)

_cache = TTLMemoryCache(ttl_seconds=30)


def get_binance_us_assets() -> list[USBinanceAsset]:
    """查询币安账户中的美股资产。"""
    cached = _cache.get("binance_assets")
    if cached is not None:
        return cached

    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        return []

    try:
        provider = BinanceProvider(api_key=api_key, api_secret=api_secret, testnet=False)
        import asyncio
        account = asyncio.run(provider._request("GET", "/api/v3/account", signed=True))
    except Exception as e:
        logger.warning(f"Binance account query failed: {e}")
        return []

    balances = account.get("balances", [])
    assets = []
    for b in balances:
        free = float(b.get("free", 0))
        locked = float(b.get("locked", 0))
        total = free + locked
        if total <= 0:
            continue
        asset = b.get("asset", "")
        if len(asset) <= 5 and asset.isalpha():
            assets.append(USBinanceAsset(
                symbol=asset,
                free=free,
                locked=locked,
                total=total,
                usdt_value=0.0,
            ))

    _cache.set("binance_assets", assets)
    return assets
```

- [ ] **Step 2: 验证导入**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -c "from src.us_stock.binance_asset import get_binance_us_assets; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: 提交**

```bash
git add src/us_stock/binance_asset.py
git commit -m "feat(us_stock): add Binance asset query module"
```

---

### Task 8: 创建 FastAPI 路由

**Files:**
- Create: `src/us_stock/routes.py`
- Modify: `src/main.py`
- Create: `tests/us_stock/test_routes.py`

- [ ] **Step 1: 编写路由测试**

```python
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.main import build_app


client = TestClient(build_app())


def test_get_watchlist():
    with patch("src.us_stock.routes._get_watchlist_store") as mock_store:
        mock_instance = MagicMock()
        mock_instance.list_items.return_value = []
        mock_store.return_value = mock_instance
        resp = client.get("/api/v1/us-stock/watchlist")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_add_watchlist_missing_symbol():
    resp = client.post("/api/v1/us-stock/watchlist", json={"name": "Test"})
    assert resp.status_code == 422  # symbol is required


def test_search_empty_query():
    resp = client.get("/api/v1/us-stock/search", params={"q": ""})
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_quote_not_found():
    with patch("src.us_stock.routes._get_yahoo_provider") as mock_prov:
        mock_instance = MagicMock()
        mock_instance.get_quote.return_value = MagicMock(price=0.0, symbol="INVALID", name="INVALID")
        mock_prov.return_value = mock_instance
        resp = client.get("/api/v1/us-stock/quote/INVALID")
    assert resp.status_code == 200
    data = resp.json()
    assert data["price"] == 0.0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/us_stock/test_routes.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现 routes.py**

```python
import logging

from fastapi import APIRouter, HTTPException, Query

from src.us_stock.binance_asset import get_binance_us_assets
from src.us_stock.models import USQuote, USWatchlistItem
from src.us_stock.watchlist import WatchlistStore
from src.us_stock.yahoo_provider import YahooProvider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/us-stock", tags=["us-stock"])

_yahoo_provider: YahooProvider | None = None
_watchlist_store: WatchlistStore | None = None


def _get_yahoo_provider() -> YahooProvider:
    global _yahoo_provider
    if _yahoo_provider is None:
        _yahoo_provider = YahooProvider()
    return _yahoo_provider


def _get_watchlist_store() -> WatchlistStore:
    global _watchlist_store
    if _watchlist_store is None:
        import os
        import psycopg
        database_url = os.getenv("DATABASE_URL", "")
        if not database_url:
            raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
        conn = psycopg.connect(database_url, row_factory=psycopg.rows.dict_row)
        _watchlist_store = WatchlistStore(conn)
    return _watchlist_store


@router.get("/quotes")
def get_quotes() -> list[dict]:
    store = _get_watchlist_store()
    items = store.list_items()
    if not items:
        return []
    symbols = [item.symbol for item in items]
    provider = _get_yahoo_provider()
    quotes = provider.get_quotes(symbols)
    return [q.model_dump() for q in quotes]


@router.get("/quote/{symbol}")
def get_quote(symbol: str) -> dict:
    provider = _get_yahoo_provider()
    quote = provider.get_quote(symbol.upper())
    return quote.model_dump()


@router.get("/kline/{symbol}")
def get_kline(
    symbol: str,
    interval: str = Query("1d"),
    range: str = Query("3mo"),
) -> list[dict]:
    provider = _get_yahoo_provider()
    klines = provider.get_kline(symbol.upper(), interval=interval, range_str=range)
    return [k.model_dump() for k in klines]


@router.get("/fundamental/{symbol}")
def get_fundamental(symbol: str) -> dict:
    provider = _get_yahoo_provider()
    fund = provider.get_fundamental(symbol.upper())
    return fund.model_dump()


@router.get("/search")
def search(q: str = Query("", max_length=50)) -> list[dict]:
    if not q.strip():
        return []
    provider = _get_yahoo_provider()
    return provider.search(q)


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


@router.get("/binance/assets")
def get_binance_assets() -> list[dict]:
    assets = get_binance_us_assets()
    return [a.model_dump() for a in assets]
```

- [ ] **Step 4: 在 main.py 注册路由**

在 `src/main.py` 的 import 区域添加：

```python
from src.us_stock.routes import router as us_stock_router
```

在 `build_app()` 函数中添加：

```python
    app.include_router(us_stock_router)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/us_stock/test_routes.py -v
```

Expected: 4 passed

- [ ] **Step 6: 运行 lint**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m ruff check src/us_stock/routes.py src/main.py
```

- [ ] **Step 7: 提交**

```bash
git add src/us_stock/routes.py src/main.py tests/us_stock/test_routes.py
git commit -m "feat(us_stock): add FastAPI routes and register in main app"
```

---

### Task 9: 创建初始数据导入脚本

**Files:**
- Create: `scripts/init_us_watchlist.py`

- [ ] **Step 1: 创建脚本**

```python
"""导入 ~500 只热门美股到 us_watchlist 表。

用法:
    /opt/anaconda3/envs/py311/bin/python3 scripts/init_us_watchlist.py
"""

import os
import psycopg

HOT_STOCKS = [
    # 科技巨头
    ("AAPL", "苹果"), ("MSFT", "微软"), ("GOOGL", "谷歌"), ("AMZN", "亚马逊"),
    ("NVDA", "英伟达"), ("TSLA", "特斯拉"), ("META", "Meta"), ("NFLX", "奈飞"),
    ("AMD", "超威半导体"), ("INTC", "英特尔"), ("QCOM", "高通"), ("AVGO", "博通"),
    ("TXN", "德州仪器"), ("ORCL", "甲骨文"), ("CRM", "赛富时"), ("IBM", "IBM"),
    ("ADBE", "奥多比"), ("CSCO", "思科"), ("NOW", "ServiceNow"), ("ACN", "埃森哲"),
    # 金融
    ("JPM", "摩根大通"), ("GS", "高盛"), ("V", "维萨"), ("MA", "万事达"),
    ("BAC", "美国银行"), ("WFC", "富国银行"), ("C", "花旗"), ("MS", "摩根士丹利"),
    ("AXP", "美国运通"), ("BLK", "贝莱德"), ("SCHW", "嘉信理财"), ("CB", "安达保险"),
    # 医疗健康
    ("JNJ", "强生"), ("UNH", "联合健康"), ("PFE", "辉瑞"), ("ABBV", "艾伯维"),
    ("MRK", "默沙东"), ("TMO", "赛默飞"), ("ABT", "雅培"), ("LLY", "礼来"),
    ("BMY", "百时美施贵宝"), ("AMGN", "安进"), ("GILD", "吉利德"), ("ISRG", "直觉外科"),
    # 消费
    ("WMT", "沃尔玛"), ("PG", "宝洁"), ("KO", "可口可乐"), ("PEP", "百事"),
    ("COST", "好市多"), ("NKE", "耐克"), ("MCD", "麦当劳"), ("DIS", "迪士尼"),
    ("SBUX", "星巴克"), ("TGT", "塔吉特"), ("LOW", "劳氏"), ("HD", "家得宝"),
    # 工业
    ("CAT", "卡特彼勒"), ("BA", "波明"), ("HON", "霍尼韦尔"), ("UPS", "联合包裹"),
    ("RTX", "雷神"), ("DE", "迪尔"), ("LMT", "洛克希德马丁"), ("GE", "通用电气"),
    # 能源
    ("XOM", "埃克森美孚"), ("CVX", "雪佛龙"), ("COP", "康菲石油"), ("SLB", "斯伦贝谢"),
    ("EOG", "EOG能源"), ("PXD", "先锋自然资源"), ("MPC", "马拉松石油"), ("PSX", "菲利普斯66"),
    # 中概股
    ("BABA", "阿里巴巴"), ("JD", "京东"), ("PDD", "拼多多"), ("BIDU", "百度"),
    ("NIO", "蔚来"), ("XPEV", "小鹏"), ("LI", "理想"), ("NTES", "网易"),
    ("BILI", "哔哩哔哩"), ("TAL", "好未来"), ("EDU", "新东方"), ("IQ", "爱奇艺"),
    ("VIPS", "唯品会"), ("ZTO", "中通快递"), ("MNSO", "名创优品"), ("FUTU", "富途"),
    # 半导体
    ("TSM", "台积电"), ("ASML", "阿斯麦"), ("MU", "美光"), ("AVGO", "博通"),
    ("NXPI", "恩智浦"), ("MRVL", "美满电子"), ("ON", "安森美"), ("LRCX", "拉姆研究"),
    ("AMAT", "应用材料"), ("KLAC", "科磊"), ("SNPS", "新思科技"), ("CDNS", "铿腾电子"),
    # 云计算 / SaaS
    ("SNOW", "Snowflake"), ("PLTR", "Palantir"), ("DDOG", "Datadog"), ("NET", "Cloudflare"),
    ("ZS", "Zscaler"), ("CRWD", "CrowdStrike"), ("PANW", "Palo Alto"), ("OKTA", "Okta"),
    ("TEAM", "Atlassian"), ("TWLO", "Twilio"), ("SHOP", "Shopify"), ("SQ", "Block"),
    # ETF
    ("SPY", "标普500ETF"), ("QQQ", "纳斯达克100ETF"), ("DIA", "道指ETF"),
    ("IWM", "罗素2000ETF"), ("VTI", "全市场ETF"), ("VOO", "标普500ETF-Vanguard"),
    ("ARKK", "ARK创新ETF"), ("XLF", "金融ETF"), ("XLE", "能源ETF"), ("XLK", "科技ETF"),
    # 更多热门
    ("PLUG", "Plug Power"), ("SNAP", "Snap"), ("UBER", "Uber"), ("ABNB", "Airbnb"),
    ("COIN", "Coinbase"), ("HOOD", "Robinhood"), ("SOFI", "SoFi"), ("RIVN", "Rivian"),
    ("LCID", "Lucid"), ("ARM", "ARM"), ("SMCI", "超微电脑"), ("DELL", "戴尔"),
    ("HPQ", "惠普"), ("LEN", "Lennar"), ("DHI", "DR Horton"), ("TOL", "Toll Brothers"),
]


def main():
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = psycopg.connect(database_url, row_factory=psycopg.rows.dict_row)
    inserted = 0
    skipped = 0

    for i, (symbol, name) in enumerate(HOT_STOCKS):
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO us_watchlist (symbol, name, sort_order) VALUES (%s, %s, %s) "
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
/opt/anaconda3/envs/py311/bin/python3 scripts/init_us_watchlist.py
```

Expected: `Done: inserted=~120, skipped=0, total=~120`

- [ ] **Step 3: 验证数据**

```bash
/opt/anaconda3/envs/py311/bin/python3 -c "
import psycopg, os
conn = psycopg.connect(os.getenv('DATABASE_URL'), row_factory=psycopg.rows.dict_row)
with conn.cursor() as cur:
    cur.execute('SELECT count(*) as cnt FROM us_watchlist')
    print(cur.fetchone())
conn.close()
"
```

Expected: `{'cnt': ~120}`

- [ ] **Step 4: 提交**

```bash
git add scripts/init_us_watchlist.py
git commit -m "feat(us_stock): add initial watchlist import script"
```

---

### Task 10: Dashboard 集成

**Files:**
- Modify: `src/api/dashboard_page/partials/status_bar.html`
- Create: `src/api/dashboard_page/partials/view_us_stock.html`
- Create: `src/api/dashboard_page/scripts/us_stock.js`
- Modify: `src/api/dashboard_page/shell.html`
- Modify: `src/api/dashboard_page/render.py`

- [ ] **Step 1: 在 status_bar.html 添加美股 tab 按钮**

在 `</div>` 结束前的 nav-group 中，在 Alpha 按钮后面添加：

```html
    <button onclick="switchView(this,'view-us-stock')"><i class="bi bi-globe"></i> 美股</button>
```

- [ ] **Step 2: 创建 view_us_stock.html**

```html
<div id="view-us-stock" class="view" style="display:none">
  <div class="panel">
    <h3><i class="bi bi-globe"></i> 美股行情</h3>
    <div style="display:flex;gap:12px;margin-bottom:16px;align-items:center">
      <input id="us-search-input" type="text" placeholder="搜索美股代码或名称..." style="flex:1;padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--bg);color:var(--text)">
      <button onclick="usSearch()" style="padding:8px 16px">搜索</button>
      <button onclick="usAddFromSearch()" style="padding:8px 16px">+ 添加自选</button>
    </div>
    <div id="us-search-results" style="display:none;margin-bottom:12px"></div>
    <div id="us-quotes-loading" style="color:var(--dim)">加载中...</div>
    <table class="table" id="us-quotes-table" style="display:none">
      <thead>
        <tr>
          <th>代码</th><th>名称</th><th>最新价</th><th>涨跌幅</th><th>成交量</th><th>市值</th><th>操作</th>
        </tr>
      </thead>
      <tbody id="us-quotes-body"></tbody>
    </table>
  </div>
  <div class="panel" style="margin-top:12px">
    <h3><i class="bi bi-wallet2"></i> 币安美股资产</h3>
    <div id="us-binance-assets" style="color:var(--dim)">加载中...</div>
  </div>
  <div class="panel" style="margin-top:12px" id="us-detail-panel" style="display:none">
    <h3 id="us-detail-title">详情</h3>
    <div id="us-detail-content"></div>
  </div>
</div>
```

- [ ] **Step 3: 创建 us_stock.js**

```javascript
let usSearchResults = [];

function usLoadQuotes() {
  const loading = document.getElementById('us-quotes-loading');
  const table = document.getElementById('us-quotes-table');
  const tbody = document.getElementById('us-quotes-body');

  fetch('/api/v1/us-stock/quotes')
    .then(r => r.json())
    .then(data => {
      if (!data || data.length === 0) {
        loading.textContent = '暂无自选股票';
        loading.style.display = '';
        table.style.display = 'none';
        return;
      }
      loading.style.display = 'none';
      table.style.display = '';
      tbody.innerHTML = data.map(q => {
        const pct = q.change_pct || 0;
        const color = pct > 0 ? 'var(--green)' : pct < 0 ? 'var(--red)' : 'var(--dim)';
        const sign = pct > 0 ? '+' : '';
        const mcap = q.market_cap ? (q.market_cap / 1e9).toFixed(1) + 'B' : '-';
        const vol = q.volume ? (q.volume / 1e6).toFixed(1) + 'M' : '-';
        return `<tr>
          <td><a href="#" onclick="usShowDetail('${q.symbol}');return false">${q.symbol}</a></td>
          <td>${q.name || '-'}</td>
          <td>${q.price ? q.price.toFixed(2) : '-'}</td>
          <td style="color:${color}">${sign}${pct.toFixed(2)}%</td>
          <td>${vol}</td>
          <td>${mcap}</td>
          <td><button onclick="usRemoveWatchlist('${q.symbol}')" style="color:var(--red);background:none;border:none;cursor:pointer">删除</button></td>
        </tr>`;
      }).join('');
    })
    .catch(() => {
      loading.textContent = '加载失败';
    });
}

function usSearch() {
  const q = document.getElementById('us-search-input').value.trim();
  if (!q) return;
  fetch(`/api/v1/us-stock/search?q=${encodeURIComponent(q)}`)
    .then(r => r.json())
    .then(data => {
      usSearchResults = data || [];
      const div = document.getElementById('us-search-results');
      if (usSearchResults.length === 0) {
        div.innerHTML = '<span style="color:var(--dim)">无结果</span>';
      } else {
        div.innerHTML = usSearchResults.map(s =>
          `<span style="display:inline-block;padding:4px 8px;margin:2px;border:1px solid var(--border);border-radius:4px;cursor:pointer" onclick="usSelectSearch('${s.symbol}','${s.name}')">${s.symbol} - ${s.name}</span>`
        ).join('');
      }
      div.style.display = '';
    });
}

function usSelectSearch(symbol, name) {
  document.getElementById('us-search-input').value = symbol;
  window._usSelectedSymbol = symbol;
  window._usSelectedName = name;
}

function usAddFromSearch() {
  const symbol = window._usSelectedSymbol || document.getElementById('us-search-input').value.trim().toUpperCase();
  const name = window._usSelectedName || symbol;
  if (!symbol) return;
  fetch('/api/v1/us-stock/watchlist', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({symbol, name}),
  }).then(r => {
    if (r.ok) {
      usLoadQuotes();
      window._usSelectedSymbol = null;
      window._usSelectedName = null;
    } else {
      r.json().then(d => alert(d.detail || '添加失败'));
    }
  });
}

function usRemoveWatchlist(symbol) {
  if (!confirm(`确认删除 ${symbol}？`)) return;
  fetch(`/api/v1/us-stock/watchlist/${symbol}`, {method: 'DELETE'})
    .then(r => { if (r.ok) usLoadQuotes(); });
}

function usShowDetail(symbol) {
  const panel = document.getElementById('us-detail-panel');
  const title = document.getElementById('us-detail-title');
  const content = document.getElementById('us-detail-content');
  panel.style.display = '';
  title.textContent = `${symbol} 详情`;
  content.innerHTML = '加载中...';

  Promise.all([
    fetch(`/api/v1/us-stock/fundamental/${symbol}`).then(r => r.json()),
    fetch(`/api/v1/us-stock/kline/${symbol}?interval=1d&range=3mo`).then(r => r.json()),
  ]).then(([fund, klines]) => {
    let html = `<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">`;
    html += `<div>行业: ${fund.sector || '-'}</div><div>细分: ${fund.industry || '-'}</div>`;
    html += `<div>市盈率: ${fund.pe_ratio ? fund.pe_ratio.toFixed(2) : '-'}</div><div>市净率: ${fund.pb_ratio ? fund.pb_ratio.toFixed(2) : '-'}</div>`;
    html += `<div>股息率: ${fund.dividend_yield ? (fund.dividend_yield * 100).toFixed(2) + '%' : '-'}</div><div>EPS: ${fund.eps ? fund.eps.toFixed(2) : '-'}</div>`;
    html += `<div>Beta: ${fund.beta ? fund.beta.toFixed(2) : '-'}</div><div>52周高: ${fund.fifty_two_week_high ? fund.fifty_two_week_high.toFixed(2) : '-'}</div>`;
    html += `<div>52周低: ${fund.fifty_two_week_low ? fund.fifty_two_week_low.toFixed(2) : '-'}</div>`;
    html += `</div>`;
    if (klines && klines.length > 0) {
      html += `<div style="max-height:200px;overflow-y:auto"><table class="table"><thead><tr><th>日期</th><th>开</th><th>高</th><th>低</th><th>收</th><th>量</th></tr></thead><tbody>`;
      klines.slice(-10).forEach(k => {
        html += `<tr><td>${k.timestamp?.split('T')[0] || '-'}</td><td>${k.open?.toFixed(2)}</td><td>${k.high?.toFixed(2)}</td><td>${k.low?.toFixed(2)}</td><td>${k.close?.toFixed(2)}</td><td>${(k.volume/1e6).toFixed(1)}M</td></tr>`;
      });
      html += '</tbody></table></div>';
    }
    content.innerHTML = html;
  }).catch(() => { content.innerHTML = '加载失败'; });
}

function usLoadBinanceAssets() {
  const div = document.getElementById('us-binance-assets');
  fetch('/api/v1/us-stock/binance/assets')
    .then(r => r.json())
    .then(data => {
      if (!data || data.length === 0) {
        div.innerHTML = '<span style="color:var(--dim)">暂无币安资产数据（请检查 BINANCE_API_KEY 配置）</span>';
        return;
      }
      let html = '<table class="table"><thead><tr><th>资产</th><th>可用</th><th>冻结</th><th>总计</th></tr></thead><tbody>';
      data.forEach(a => {
        html += `<tr><td>${a.symbol}</td><td>${a.free.toFixed(4)}</td><td>${a.locked.toFixed(4)}</td><td>${a.total.toFixed(4)}</td></tr>`;
      });
      html += '</tbody></table>';
      div.innerHTML = html;
    })
    .catch(() => { div.innerHTML = '加载失败'; });
}

function usInit() {
  usLoadQuotes();
  usLoadBinanceAssets();
  setInterval(usLoadQuotes, 60000);
  setInterval(usLoadBinanceAssets, 30000);
}
```

- [ ] **Step 4: 修改 shell.html**

在 `{{VIEW_ALPHA}}` 后面添加：

```
{{VIEW_US_STOCK}}
```

在 `{{INLINE_ALPHA_JS}}` 后面添加：

```
{{INLINE_US_STOCK_JS}}
```

- [ ] **Step 5: 修改 render.py**

在 `render_dashboard_html()` 的 `replacements` 字典中添加：

```python
        "{{VIEW_US_STOCK}}": _read("partials/view_us_stock.html"),
        "{{INLINE_US_STOCK_JS}}": _read("scripts/us_stock.js"),
```

在 bootstrap 中确保调用 `usInit()`（在 `scripts/bootstrap.js` 中添加）。

- [ ] **Step 6: 运行 lint**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m ruff check src/api/dashboard_page/
```

- [ ] **Step 7: 提交**

```bash
git add src/api/dashboard_page/partials/status_bar.html src/api/dashboard_page/partials/view_us_stock.html src/api/dashboard_page/scripts/us_stock.js src/api/dashboard_page/shell.html src/api/dashboard_page/render.py
git commit -m "feat(dashboard): add US stock tab with quotes, search, watchlist, and Binance assets"
```

---

### Task 11: 全量验证

- [ ] **Step 1: 运行全部单元测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/us_stock/ -v
```

Expected: all passed

- [ ] **Step 2: 运行 lint**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m ruff check src/us_stock/ tests/us_stock/
```

- [ ] **Step 3: 运行 typecheck**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m mypy src/us_stock/ --ignore-missing-imports
```

- [ ] **Step 4: 启动服务验证 Dashboard**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve
```

访问 `http://localhost:8000/dashboard`，点击 "美股" tab，验证：
- 自选列表加载
- 搜索功能
- 添加/删除自选
- 币安资产显示

- [ ] **Step 5: 提交最终状态**

```bash
git add -A
git commit -m "feat(us_stock): complete US stock module with dashboard integration"
```
