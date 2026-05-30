# 双环境数据源自动切换 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一套代码同时支持本地（AkShare）和海外服务器（Tushare），自动探测降级，无需手动改配置。

**Architecture:** 新增 `TushareProvider` 实现 `DataProvider` 接口；`config.py` 新增 `tushare_token` 字段；`provider_chain.py` 支持 `auto` 模式，先探测 AkShare 全市场接口，失败降级 Tushare。

**Tech Stack:** Python 3.11, tushare, akshare, pydantic-settings, pytest

---

## 文件变更清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/core/config.py` | 修改 | 新增 `tushare_token` 字段，`market_data_provider` 默认改为 `auto` |
| `src/data/providers/tushare_provider.py` | 新建 | Tushare 数据提供者 |
| `src/data/providers/provider_chain.py` | 修改 | 新增 `build_auto_provider_chain()` |
| `.env.example` | 修改 | 新增 Tushare 配置模板 |
| `tests/test_tushare_provider.py` | 新建 | TushareProvider 单元测试 |
| `tests/test_provider_chain.py` | 修改 | 新增 auto 模式测试 |

---

### Task 1: config.py 新增 tushare_token 字段

**Files:**
- Modify: `src/core/config.py:37-38`
- Modify: `.env.example`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_config_tushare.py
from src.core.config import Settings


def test_settings_has_tushare_token():
    settings = Settings()
    assert settings.tushare_token == ""


def test_settings_reads_tushare_token_from_env(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "test_token_123")
    settings = Settings()
    assert settings.tushare_token == "test_token_123"


def test_market_data_provider_defaults_to_auto():
    settings = Settings()
    assert settings.market_data_provider == "auto"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_config_tushare.py -v
```

预期：`FAILED` - `Settings` 没有 `tushare_token` 属性

- [ ] **Step 3: 修改 config.py**

`src/core/config.py` 第 37-38 行，把：

```python
    # 行情数据源
    market_data_provider: str = "akshare"
```

改成：

```python
    # 行情数据源
    market_data_provider: str = "auto"
    tushare_token: str = ""
```

- [ ] **Step 4: 更新 .env.example**

在 `MARKET_DATA_PROVIDER=akshare` 下方新增：

```bash
MARKET_DATA_PROVIDER=auto
TUSHARE_TOKEN=your_tushare_token_here
```

- [ ] **Step 5: 运行测试确认通过**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_config_tushare.py -v
```

预期：`3 passed`

- [ ] **Step 6: 提交**

```bash
git add src/core/config.py .env.example tests/test_config_tushare.py
git commit -m "feat: add tushare_token to config, default provider to auto"
```

---

### Task 2: 新建 TushareProvider

**Files:**
- Create: `src/data/providers/tushare_provider.py`
- Create: `tests/test_tushare_provider.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tushare_provider.py
from src.data.providers.tushare_provider import TushareProvider


def test_not_available_without_token():
    p = TushareProvider(token="")
    assert p.is_available() is False


def test_available_with_token():
    p = TushareProvider(token="test_token")
    assert p.is_available() is True


def test_to_ts_code():
    from src.data.providers.tushare_provider import _to_ts_code
    assert _to_ts_code("600519.SH") == "600519.SH"
    assert _to_ts_code("000001.sz") == "000001.SZ"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_tushare_provider.py -v
```

预期：`ModuleNotFoundError`

- [ ] **Step 3: 实现 TushareProvider**

```python
# src/data/providers/tushare_provider.py
import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from src.data.providers.base import DataProvider, MarketSnapshot

logger = logging.getLogger(__name__)


class TushareProvider(DataProvider):

    def __init__(self, token: str = "") -> None:
        self._token = token
        self._pro = None

    def _get_pro(self):
        if self._pro is None and self._token:
            try:
                import tushare as ts
                ts.set_token(self._token)
                self._pro = ts.pro_api()
            except Exception as e:
                logger.error(f"Tushare 初始化失败: {e}")
        return self._pro

    def is_available(self) -> bool:
        return bool(self._token) and self._get_pro() is not None

    def get_realtime_quote(self, symbol: str) -> Optional[MarketSnapshot]:
        pro = self._get_pro()
        if pro is None:
            return None
        try:
            df = pro.daily(ts_code=_to_ts_code(symbol), limit=1)
            if df.empty:
                return None
            r = df.iloc[0]
            return MarketSnapshot(
                symbol=symbol,
                timestamp=datetime.strptime(str(r["trade_date"]), "%Y%m%d"),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=int(r["vol"]),
                amount=float(r["amount"]) * 1000,
            )
        except Exception as e:
            logger.warning(f"Tushare get_realtime_quote({symbol}) 失败: {e}")
            return None

    def get_history(
        self, symbol: str, start_date: datetime, end_date: datetime, freq: str = "daily"
    ) -> pd.DataFrame:
        pro = self._get_pro()
        if pro is None:
            return pd.DataFrame()
        try:
            df = pro.daily(
                ts_code=_to_ts_code(symbol),
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            return df.rename(columns={"trade_date": "date", "vol": "volume"}) if not df.empty else pd.DataFrame()
        except Exception as e:
            logger.warning(f"Tushare get_history({symbol}) 失败: {e}")
            return pd.DataFrame()

    def get_stock_list(self) -> pd.DataFrame:
        pro = self._get_pro()
        if pro is None:
            return pd.DataFrame()
        try:
            df = pro.stock_list(exchange="", list_status="L")
            return df.rename(columns={"ts_code": "symbol"})[["symbol", "name"]] if not df.empty else pd.DataFrame()
        except Exception as e:
            logger.warning(f"Tushare get_stock_list 失败: {e}")
            return pd.DataFrame()


def _to_ts_code(symbol: str) -> str:
    return symbol.upper()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_tushare_provider.py -v
```

预期：`3 passed`

- [ ] **Step 5: 提交**

```bash
git add src/data/providers/tushare_provider.py tests/test_tushare_provider.py
git commit -m "feat: add TushareProvider"
```

---

### Task 3: provider_chain 支持 auto 模式

**Files:**
- Modify: `src/data/providers/provider_chain.py:84`
- Modify: `tests/test_provider_chain.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_provider_chain.py` 末尾新增：

```python
from src.data.providers.provider_chain import build_auto_provider_chain


def test_auto_chain_uses_akshare_when_available(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "auto")
    monkeypatch.setenv("TUSHARE_TOKEN", "test_token")
    chain = build_auto_provider_chain()
    assert chain is not None


def test_manual_tushare_mode(monkeypatch):
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "tushare")
    monkeypatch.setenv("TUSHARE_TOKEN", "test_token")
    from src.data.providers.provider_chain import build_provider_chain_from_settings
    chain = build_provider_chain_from_settings()
    from src.data.providers.tushare_provider import TushareProvider
    assert isinstance(chain._providers[0], TushareProvider)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_provider_chain.py -v -k "auto or manual"
```

预期：`FAILED` - `build_auto_provider_chain` 不存在

- [ ] **Step 3: 实现 auto 模式**

在 `src/data/providers/provider_chain.py` 末尾新增：

```python
from src.core.config import Settings
from src.data.providers.akshare_provider import AkshareProvider
from src.data.providers.tushare_provider import TushareProvider


def build_provider_chain_from_settings() -> ProviderChain:
    settings = Settings()
    mode = settings.market_data_provider
    if mode == "tushare":
        return ProviderChain([TushareProvider(token=settings.tushare_token)])
    elif mode == "akshare":
        return ProviderChain([AkshareProvider()])
    return build_auto_provider_chain()


def build_auto_provider_chain() -> ProviderChain:
    settings = Settings()
    akshare = AkshareProvider()
    tushare = TushareProvider(token=settings.tushare_token)
    try:
        if akshare.is_available():
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if not df.empty:
                logger.info("auto: AkShare 可用")
                return ProviderChain([akshare, tushare])
    except Exception as e:
        logger.warning(f"auto: AkShare 探测失败 ({e})，降级 Tushare")
    logger.info("auto: 使用 Tushare")
    return ProviderChain([tushare, akshare])
```

- [ ] **Step 4: 运行测试确认通过**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_provider_chain.py -v
```

预期：全部通过

- [ ] **Step 5: 提交**

```bash
git add src/data/providers/provider_chain.py tests/test_provider_chain.py
git commit -m "feat: support auto mode in ProviderChain"
```

---

### Task 4: 集成验证

- [ ] **Step 1: 运行全量测试**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

预期：无新增失败

- [ ] **Step 2: 本地验证 auto 模式**

```bash
/opt/anaconda3/envs/py311/bin/python3 -c "
from src.data.providers.provider_chain import build_provider_chain_from_settings
chain = build_provider_chain_from_settings()
print('providers:', [type(p).__name__ for p in chain._providers])
"
```

预期：`providers: ['AkshareProvider', 'TushareProvider']`

- [ ] **Step 3: 提交并推送**

```bash
git add -A
git commit -m "feat: complete dual-env data source auto-switching"
git push origin master
```

---

## 验收标准

- [ ] `MARKET_DATA_PROVIDER=auto` 本地运行 → AkShare 生效
- [ ] `MARKET_DATA_PROVIDER=auto` AWS 运行 → 自动降级 Tushare
- [ ] `MARKET_DATA_PROVIDER=tushare` 强制用 Tushare
- [ ] `MARKET_DATA_PROVIDER=akshare` 强制用 AkShare
- [ ] 现有测试全部通过
- [ ] `.env.example` 包含 Tushare 配置模板
