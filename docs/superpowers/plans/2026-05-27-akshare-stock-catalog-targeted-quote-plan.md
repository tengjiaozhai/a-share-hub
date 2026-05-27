# AkShare Stock Catalog And Targeted Quote Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 先把 AkShare 的股票列表与 symbol 规范化做成权威入口，再把 `/api/v1/market/quote` 收敛为“先校验股票池、后定向返回行情”的单路径 API，最后只在行情快照刷新链路上补熔断。

**Architecture:** 当前 `AkshareProvider` 直接调用 `stock_zh_a_spot_em()` 拉全市场快照，再在 DataFrame 里筛 symbol，这导致 404 混淆了“非法股票”和“上游不可用”，也让每次查询都绑死在一条不稳定的外部链路上。下一步把实现拆成三个清晰职责：股票列表缓存与 symbol 规范化、行情快照缓存与按 code 取行、API 错误分级；熔断只包行情快照刷新，不影响股票列表查询。

**Tech Stack:** Python 3.11, FastAPI, AkShare, pandas, pytest

---

## File Structure

- Create: `src/data/providers/akshare_catalog.py`
  - 负责股票列表拉取后的标准化、`000858 -> 000858.SZ` 规范化、按交易所/关键字筛选、内存 TTL 缓存。
- Create: `src/data/providers/akshare_errors.py`
  - 负责定义 `AkshareSymbolNotFoundError`、`AkshareUpstreamError`、`AkshareBreakerOpenError`，避免再用 `None` 吞掉真实失败原因。
- Create: `src/data/providers/akshare_snapshot_cache.py`
  - 负责 `stock_zh_a_spot_em()` 的短 TTL 缓存、按 code 找行、失败计数与熔断窗口。
- Modify: `src/data/providers/akshare_provider.py`
  - 只负责编排 catalog 和 snapshot cache，输出 `MarketSnapshot`。
- Modify: `src/api/routes_market.py`
  - 新增 `GET /api/v1/market/stocks`，并把 `GET /api/v1/market/quote` 改成区分 `404/503`。
- Create: `tests/test_akshare_catalog.py`
  - 覆盖 symbol 规范化、列表标准化、按交易所/关键字筛选。
- Create: `tests/test_akshare_snapshot_cache.py`
  - 覆盖快照缓存命中、快照失效刷新、熔断打开后短路。
- Modify: `tests/test_market_quote_api.py`
  - 把“上游返回 None -> 404”改成“非法 symbol -> 404；上游失败 -> 503”。
- Create: `tests/test_market_stock_list_api.py`
  - 覆盖 `/api/v1/market/stocks` 的查询、筛选、limit。
- Modify: `docs/runbooks/dashboard_user_guide.md`
  - 记录新接口、symbol 格式、错误含义。

## Scope

- 本计划只覆盖 AkShare 单 provider 路径，不在这一轮引入雪球、Tushare、Redis 或前端 autocomplete。
- 本计划不改变 `DataProvider` 抽象接口，只在 `AkshareProvider` 内部新增私有协作者。
- 本计划不把 `stock_individual_info_em()` 作为行情主路径，因为它不返回当前 `MarketSnapshot` 需要的完整 OHLCV 字段。

### Task 1: Build Stock Catalog And Symbol Normalization

**Files:**
- Create: `src/data/providers/akshare_catalog.py`
- Test: `tests/test_akshare_catalog.py`

- [ ] **Step 1: Write the failing test**

```python
import pandas as pd

from src.data.providers.akshare_catalog import (
    StockCatalogCache,
    infer_exchange,
    normalize_symbol,
    normalize_stock_list_frame,
)


def test_normalize_symbol_infers_exchange_from_code():
    assert normalize_symbol("000858") == "000858.SZ"
    assert normalize_symbol("600519") == "600519.SH"
    assert normalize_symbol("920001") == "920001.BJ"
    assert normalize_symbol("sz000858") == "000858.SZ"


def test_normalize_stock_list_frame_adds_symbol_and_exchange():
    raw = pd.DataFrame(
        [
            {"code": "000858", "name": "五 粮 液"},
            {"code": "600519", "name": "贵州茅台"},
        ]
    )

    frame = normalize_stock_list_frame(raw)

    assert frame.to_dict("records") == [
        {"symbol": "000858.SZ", "code": "000858", "name": "五 粮 液", "exchange": "SZ"},
        {"symbol": "600519.SH", "code": "600519", "name": "贵州茅台", "exchange": "SH"},
    ]


def test_catalog_cache_filters_by_query_and_exchange():
    cache = StockCatalogCache(ttl_seconds=300)
    cache._frame = pd.DataFrame(
        [
            {"symbol": "000858.SZ", "code": "000858", "name": "五 粮 液", "exchange": "SZ"},
            {"symbol": "600519.SH", "code": "600519", "name": "贵州茅台", "exchange": "SH"},
            {"symbol": "920001.BJ", "code": "920001", "name": "纬达光电", "exchange": "BJ"},
        ]
    )

    records = cache.search(query="粮", exchange="SZ", limit=10)

    assert records == [
        {"symbol": "000858.SZ", "code": "000858", "name": "五 粮 液", "exchange": "SZ"}
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_akshare_catalog.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src.data.providers.akshare_catalog'`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

import pandas as pd


def infer_exchange(code: str) -> str:
    if code.startswith(("600", "601", "603", "605", "688", "689", "900")):
        return "SH"
    if code.startswith(("000", "001", "002", "003", "300", "301", "200")):
        return "SZ"
    if code.startswith(("430", "440", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "874", "875", "876", "877", "878", "879", "920")):
        return "BJ"
    raise ValueError(f"unsupported stock code: {code}")


def normalize_symbol(symbol: str) -> str:
    text = symbol.strip().upper().replace("-", ".")
    if "." in text:
        code, exchange = text.split(".", 1)
        return f"{code}.{exchange}"
    if text.startswith(("SH", "SZ", "BJ")) and text[2:].isdigit():
        return f"{text[2:]}.{text[:2]}"
    return f"{text}.{infer_exchange(text)}"


def normalize_stock_list_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.rename(columns={"code": "code", "name": "name"})[["code", "name"]].copy()
    normalized["code"] = normalized["code"].astype(str).str.zfill(6)
    normalized["exchange"] = normalized["code"].map(infer_exchange)
    normalized["symbol"] = normalized["code"] + "." + normalized["exchange"]
    return normalized[["symbol", "code", "name", "exchange"]]


@dataclass
class StockCatalogCache:
    ttl_seconds: int = 86400
    _frame: pd.DataFrame | None = None
    _expires_at: datetime | None = None

    def load(self, fetcher: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        now = datetime.utcnow()
        if self._frame is not None and self._expires_at is not None and now < self._expires_at:
            return self._frame
        frame = normalize_stock_list_frame(fetcher())
        self._frame = frame
        self._expires_at = now + timedelta(seconds=self.ttl_seconds)
        return frame

    def search(self, query: str = "", exchange: str = "all", limit: int = 50) -> list[dict]:
        frame = self._frame if self._frame is not None else pd.DataFrame(columns=["symbol", "code", "name", "exchange"])
        query_text = query.strip()
        exchange_text = exchange.strip().upper()
        if exchange_text and exchange_text != "ALL":
            frame = frame[frame["exchange"] == exchange_text]
        if query_text:
            frame = frame[
                frame["symbol"].str.contains(query_text, case=False, na=False)
                | frame["code"].str.contains(query_text, case=False, na=False)
                | frame["name"].str.contains(query_text, case=False, na=False)
            ]
        return frame.head(limit).to_dict("records")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_akshare_catalog.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/data/providers/akshare_catalog.py tests/test_akshare_catalog.py
git commit -m "feat: add akshare stock catalog cache"
```

### Task 2: Add Snapshot Cache For Targeted Quote Lookup

**Files:**
- Create: `src/data/providers/akshare_errors.py`
- Create: `src/data/providers/akshare_snapshot_cache.py`
- Modify: `src/data/providers/akshare_provider.py`
- Test: `tests/test_akshare_snapshot_cache.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.data.providers.akshare_errors import AkshareBreakerOpenError, AkshareUpstreamError
from src.data.providers.akshare_snapshot_cache import SpotSnapshotCache


def test_snapshot_cache_returns_matching_row_without_refetch():
    calls = {"count": 0}

    def fetcher():
        calls["count"] += 1
        return pd.DataFrame(
            [
                {"代码": "000858", "名称": "五 粮 液", "最新价": 128.52, "今开": 127.80, "最高": 129.00, "最低": 127.10, "成交量": 123456, "成交额": 987654321.0},
            ]
        )

    cache = SpotSnapshotCache(ttl_seconds=10, failure_threshold=3, open_seconds=30)

    first = cache.get_row("000858", fetcher)
    second = cache.get_row("000858", fetcher)

    assert first["代码"] == "000858"
    assert second["代码"] == "000858"
    assert calls["count"] == 1


def test_snapshot_cache_opens_breaker_after_repeated_failures():
    calls = {"count": 0}

    def fetcher():
        calls["count"] += 1
        raise RuntimeError("upstream reset")

    cache = SpotSnapshotCache(ttl_seconds=10, failure_threshold=2, open_seconds=60)

    with pytest.raises(AkshareUpstreamError):
        cache.get_row("000858", fetcher)
    with pytest.raises(AkshareUpstreamError):
        cache.get_row("000858", fetcher)
    with pytest.raises(AkshareBreakerOpenError):
        cache.get_row("000858", fetcher)

    assert calls["count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_akshare_snapshot_cache.py -v`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

import pandas as pd


class AkshareUpstreamError(RuntimeError):
    pass


class AkshareBreakerOpenError(RuntimeError):
    pass
```

```python
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable

import pandas as pd

from src.data.providers.akshare_errors import AkshareBreakerOpenError, AkshareUpstreamError


class SpotSnapshotCache:
    def __init__(self, ttl_seconds: int = 10, failure_threshold: int = 3, open_seconds: int = 30):
        self.ttl_seconds = ttl_seconds
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self._frame: pd.DataFrame | None = None
        self._expires_at: datetime | None = None
        self._failures = 0
        self._breaker_until: datetime | None = None

    def get_row(self, code: str, fetcher: Callable[[], pd.DataFrame]) -> pd.Series:
        frame = self._get_frame(fetcher)
        row = frame[frame["代码"] == code]
        if row.empty:
            raise KeyError(code)
        return row.iloc[0]

    def _get_frame(self, fetcher: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        now = datetime.utcnow()
        if self._breaker_until is not None and now < self._breaker_until:
            raise AkshareBreakerOpenError("akshare spot snapshot breaker is open")
        if self._frame is not None and self._expires_at is not None and now < self._expires_at:
            return self._frame
        try:
            frame = fetcher()
        except Exception as exc:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._breaker_until = now + timedelta(seconds=self.open_seconds)
            raise AkshareUpstreamError(str(exc)) from exc
        self._frame = frame
        self._expires_at = now + timedelta(seconds=self.ttl_seconds)
        self._failures = 0
        self._breaker_until = None
        return frame
```

- [ ] **Step 4: Refactor `AkshareProvider` to use catalog + snapshot cache**

```python
from src.data.providers.akshare_catalog import StockCatalogCache, normalize_symbol
from src.data.providers.akshare_errors import AkshareBreakerOpenError, AkshareUpstreamError
from src.data.providers.akshare_snapshot_cache import SpotSnapshotCache


class AkshareProvider(DataProvider):
    def __init__(
        self,
        catalog: StockCatalogCache | None = None,
        snapshot_cache: SpotSnapshotCache | None = None,
    ):
        self._catalog = catalog or StockCatalogCache()
        self._snapshot_cache = snapshot_cache or SpotSnapshotCache()

    def get_stock_list(self) -> pd.DataFrame:
        import akshare as ak

        return self._catalog.load(lambda: ak.stock_info_a_code_name())

    def get_realtime_quote(self, symbol: str) -> Optional[MarketSnapshot]:
        import akshare as ak

        normalized_symbol = normalize_symbol(symbol)
        stock_list = self.get_stock_list()
        match = stock_list[stock_list["symbol"] == normalized_symbol]
        if match.empty:
            raise KeyError(normalized_symbol)
        code = match.iloc[0]["code"]
        row = self._snapshot_cache.get_row(code, lambda: ak.stock_zh_a_spot_em())
        return MarketSnapshot(
            symbol=normalized_symbol,
            timestamp=datetime.now(),
            open=_to_float(row.get("今开"), 0.0) or 0.0,
            high=_to_float(row.get("最高"), 0.0) or 0.0,
            low=_to_float(row.get("最低"), 0.0) or 0.0,
            close=_to_float(row.get("最新价"), 0.0) or 0.0,
            volume=_to_int(row.get("成交量"), 0) or 0,
            amount=_to_float(row.get("成交额"), 0.0) or 0.0,
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_akshare_snapshot_cache.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/data/providers/akshare_errors.py src/data/providers/akshare_snapshot_cache.py src/data/providers/akshare_provider.py tests/test_akshare_snapshot_cache.py
git commit -m "feat: cache akshare spot snapshots for targeted lookup"
```

### Task 3: Add Stock List API And Fix Quote Error Semantics

**Files:**
- Modify: `src/api/routes_market.py`
- Create: `tests/test_market_stock_list_api.py`
- Modify: `tests/test_market_quote_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
from fastapi.testclient import TestClient

from src.main import build_app


class FakeAkshareProvider:
    def __init__(self):
        self.last_search = None

    def is_available(self):
        return True

    def get_stock_list(self):
        import pandas as pd

        return pd.DataFrame(
            [
                {"symbol": "000858.SZ", "code": "000858", "name": "五 粮 液", "exchange": "SZ"},
                {"symbol": "600519.SH", "code": "600519", "name": "贵州茅台", "exchange": "SH"},
            ]
        )


def test_market_stocks_returns_filtered_records(monkeypatch):
    from src.api import routes_market

    monkeypatch.setattr(routes_market, "_get_akshare_provider", lambda: FakeAkshareProvider())
    client = TestClient(build_app())

    response = client.get("/api/v1/market/stocks", params={"query": "粮", "exchange": "SZ", "limit": 10})

    assert response.status_code == 200
    assert response.json() == [
        {"symbol": "000858.SZ", "code": "000858", "name": "五 粮 液", "exchange": "SZ"}
    ]
```

```python
def test_market_quote_returns_404_for_unknown_symbol(monkeypatch):
    from src.api import routes_market

    class QuoteProvider:
        def is_available(self):
            return True

        def get_realtime_quote(self, symbol: str):
            raise KeyError(symbol)

    monkeypatch.setattr(routes_market, "_get_akshare_provider", lambda: QuoteProvider())
    client = TestClient(build_app())

    response = client.get("/api/v1/market/quote", params={"symbol": "999999.SH"})

    assert response.status_code == 404
    assert response.json()["detail"] == "quote symbol not found: 999999.SH"
```

```python
def test_market_quote_returns_503_for_upstream_failure(monkeypatch):
    from src.api import routes_market
    from src.data.providers.akshare_errors import AkshareUpstreamError

    class QuoteProvider:
        def is_available(self):
            return True

        def get_realtime_quote(self, symbol: str):
            raise AkshareUpstreamError("upstream reset")

    monkeypatch.setattr(routes_market, "_get_akshare_provider", lambda: QuoteProvider())
    client = TestClient(build_app())

    response = client.get("/api/v1/market/quote", params={"symbol": "000858.SZ"})

    assert response.status_code == 503
    assert response.json()["detail"] == "quote upstream unavailable: upstream reset"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_market_stock_list_api.py tests/test_market_quote_api.py -v`

Expected: FAIL because `/api/v1/market/stocks` does not exist and quote endpoint still maps all `None` to `404`

- [ ] **Step 3: Implement `/api/v1/market/stocks` and explicit error mapping**

```python
from fastapi import APIRouter, HTTPException, Query

from src.data.providers.akshare_errors import AkshareBreakerOpenError, AkshareUpstreamError
from src.data.providers.akshare_provider import AkshareProvider

router = APIRouter(prefix="/api/v1/market")


@router.get("/stocks")
def list_market_stocks(
    query: str = Query("", max_length=50),
    exchange: str = Query("all"),
    limit: int = Query(20, ge=1, le=200),
) -> list[dict]:
    provider = _get_akshare_provider()
    if not provider.is_available():
        raise HTTPException(status_code=503, detail="akshare provider unavailable")
    frame = provider.get_stock_list()
    records = frame.copy()
    if exchange.strip().upper() != "ALL":
        records = records[records["exchange"] == exchange.strip().upper()]
    if query.strip():
        q = query.strip()
        records = records[
            records["symbol"].str.contains(q, case=False, na=False)
            | records["code"].str.contains(q, case=False, na=False)
            | records["name"].str.contains(q, case=False, na=False)
        ]
    return records.head(limit).to_dict("records")


@router.get("/quote")
def get_market_quote(symbol: str = Query(..., min_length=3)) -> dict:
    normalized_symbol = symbol.strip().upper()
    provider = _get_akshare_provider()
    if not provider.is_available():
        raise HTTPException(status_code=503, detail="akshare provider unavailable")
    try:
        snapshot = provider.get_realtime_quote(normalized_symbol)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"quote symbol not found: {normalized_symbol}")
    except (AkshareUpstreamError, AkshareBreakerOpenError) as exc:
        raise HTTPException(status_code=503, detail=f"quote upstream unavailable: {exc}")
    return snapshot.model_dump()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_market_stock_list_api.py tests/test_market_quote_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/routes_market.py tests/test_market_stock_list_api.py tests/test_market_quote_api.py
git commit -m "feat: add market stock list API and quote error mapping"
```

### Task 4: Add Breaker Coverage And Avoid False 404s

**Files:**
- Modify: `tests/test_market_quote_api.py`
- Modify: `tests/test_akshare_snapshot_cache.py`
- Modify: `src/data/providers/akshare_provider.py`

- [ ] **Step 1: Write the failing regression tests**

```python
from src.data.providers.akshare_errors import AkshareBreakerOpenError


def test_market_quote_returns_503_when_breaker_is_open(monkeypatch):
    from src.api import routes_market

    class QuoteProvider:
        def is_available(self):
            return True

        def get_realtime_quote(self, symbol: str):
            raise AkshareBreakerOpenError("akshare spot snapshot breaker is open")

    monkeypatch.setattr(routes_market, "_get_akshare_provider", lambda: QuoteProvider())
    client = TestClient(build_app())

    response = client.get("/api/v1/market/quote", params={"symbol": "000858.SZ"})

    assert response.status_code == 503
    assert response.json()["detail"] == "quote upstream unavailable: akshare spot snapshot breaker is open"
```

```python
def test_provider_raises_key_error_only_for_missing_symbol(monkeypatch):
    import pandas as pd
    from src.data.providers.akshare_catalog import StockCatalogCache
    from src.data.providers.akshare_provider import AkshareProvider
    from src.data.providers.akshare_snapshot_cache import SpotSnapshotCache

    catalog = StockCatalogCache(ttl_seconds=300)
    snapshot_cache = SpotSnapshotCache(ttl_seconds=10, failure_threshold=3, open_seconds=30)
    provider = AkshareProvider(catalog=catalog, snapshot_cache=snapshot_cache)

    monkeypatch.setattr(
        provider,
        "get_stock_list",
        lambda: pd.DataFrame([{"symbol": "000858.SZ", "code": "000858", "name": "五 粮 液", "exchange": "SZ"}]),
    )

    with pytest.raises(KeyError):
        provider.get_realtime_quote("999999.SH")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_market_quote_api.py tests/test_akshare_snapshot_cache.py -v`

Expected: FAIL until the provider and route distinguish missing symbol from upstream failure

- [ ] **Step 3: Tighten provider behavior**

```python
def get_realtime_quote(self, symbol: str) -> Optional[MarketSnapshot]:
    import akshare as ak

    normalized_symbol = normalize_symbol(symbol)
    stock_list = self.get_stock_list()
    match = stock_list[stock_list["symbol"] == normalized_symbol]
    if match.empty:
        raise KeyError(normalized_symbol)

    code = match.iloc[0]["code"]
    row = self._snapshot_cache.get_row(code, lambda: ak.stock_zh_a_spot_em())

    last_price = _to_float(row.get("最新价"), 0.0) or 0.0
    open_price = _to_float(row.get("今开"), last_price) or last_price
    high_price = _to_float(row.get("最高"), last_price) or last_price
    low_price = _to_float(row.get("最低"), last_price) or last_price

    return MarketSnapshot(
        symbol=normalized_symbol,
        timestamp=datetime.now(),
        open=open_price,
        high=high_price,
        low=low_price,
        close=last_price,
        volume=_to_int(row.get("成交量"), 0) or 0,
        amount=_to_float(row.get("成交额"), 0.0) or 0.0,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_market_quote_api.py tests/test_akshare_snapshot_cache.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/data/providers/akshare_provider.py tests/test_market_quote_api.py tests/test_akshare_snapshot_cache.py
git commit -m "fix: distinguish missing symbols from akshare upstream failures"
```

### Task 5: Document The New Market Query Contract

**Files:**
- Modify: `docs/runbooks/dashboard_user_guide.md`

- [ ] **Step 1: Write the failing doc assertion**

```python
from pathlib import Path


def test_dashboard_runbook_mentions_market_endpoints():
    content = Path("docs/runbooks/dashboard_user_guide.md").read_text(encoding="utf-8")
    assert "/api/v1/market/stocks" in content
    assert "/api/v1/market/quote" in content
    assert "000858.SZ" in content
    assert "quote symbol not found" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_docs_alignment.py -v`

Expected: FAIL or missing assertions for the new market endpoints

- [ ] **Step 3: Update the runbook**

```md
## 行情接口

- `GET /api/v1/market/stocks?query=五粮&exchange=SZ&limit=20`
  - 返回字段：`symbol`、`code`、`name`、`exchange`
- `GET /api/v1/market/quote?symbol=000858.SZ`
  - 返回字段：`symbol`、`timestamp`、`open`、`high`、`low`、`close`、`volume`、`amount`

## 错误语义

- `404 quote symbol not found: 999999.SH`
  - 说明 symbol 不在 AkShare 股票池内
- `503 quote upstream unavailable: ...`
  - 说明股票池存在该 symbol，但实时行情上游暂时不可用或熔断已打开
```

- [ ] **Step 4: Run tests to verify docs pass**

Run: `cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_docs_alignment.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add docs/runbooks/dashboard_user_guide.md tests/test_docs_alignment.py
git commit -m "docs: describe akshare market stock and quote APIs"
```

## Acceptance Criteria

- `GET /api/v1/market/stocks` 能返回规范化后的 `symbol/code/name/exchange` 列表，并支持 `query/exchange/limit`。
- `GET /api/v1/market/quote` 不再把所有失败都返回成 `404`。
- `AkshareProvider` 的行情查询路径变成：
  - 先用股票列表校验 symbol 是否存在
  - 再从短 TTL 的实时快照缓存里按 code 取行
  - 上游连续失败后打开熔断并返回 `503`
- 新增测试全部通过，不依赖 SQLite。

## Self-Review

- 覆盖检查：本计划覆盖了“先获取股票列表”“再针对性查询行情”“最后考虑熔断”三段要求，没有把前端 autocomplete 或多 provider fallback 混进来。
- Placeholder 检查：没有 `TODO/TBD/implement later`，每个任务都给了测试、实现、命令和提交信息。
- 类型检查：`MarketSnapshot` 仍保持现有 schema；`routes_market.py` 只改错误语义，不改返回结构字段名。

Plan complete and saved to `docs/superpowers/plans/2026-05-27-akshare-stock-catalog-targeted-quote-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
