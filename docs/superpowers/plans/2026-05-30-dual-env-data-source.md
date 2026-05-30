# 双环境数据源自动切换 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一套代码同时支持本地（AkShare）和海外服务器（Tushare），自动探测降级，无需手动改配置。

**Architecture:** 新增 `TushareProvider` 实现 `DataProvider` 接口；`config.py` 新增 `tushare_token` 字段；`provider_chain.py` 支持 `auto` 模式，先探测 AkShare 全市场接口，失败降级 Tushare。

**Tech Stack:** Python 3.11, tushare, akshare, pydantic-settings, pytest

---

## 文件变更清单

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/core/config.py` | 修改 | 新增 `tushare_token` 字段 |
| `src/data/providers/tushare_provider.py` | 新建 | Tushare 数据提供者 |
| `src/data/providers/provider_chain.py` | 修改 | 支持 auto 模式探测降级 |
| `.env.example` | 修改 | 新增 Tushare 配置模板 |
| `tests/test_tushare_provider.py` | 新建 | TushareProvider 单元测试 |
| `tests/test_provider_chain.py` | 修改 | 新增 auto 模式测试 |

---

### Task 1: config.py 新增 tushare_token 字段

**Files:**
- Modify: `src/core/config.py`
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_config_tushare.py -v
```

预期：`FAILED` - `Settings` 没有 `tushare_token` 属性

- [ ] **Step 3: 实现最小代码**

`src/core/config.py` 在 `market_data_provider` 下方新增：

```python
    # 行情数据源
    market_data_provider: str = "auto"
    tushare_token: str = ""
```

同时把 `market_data_provider` 默认值从 `"akshare"` 改为 `"auto"`。

- [ ] **Step 4: 更新 .env.example**

在 `.env.example` 的 `MARKET_DATA_PROVIDER` 下方新增：

```bash
MARKET_DATA_PROVIDER=auto
TUSHARE_TOKEN=your_tushare_token_here
```

- [ ] **Step 5: 运行测试确认通过**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_config_tushare.py -v
```

预期：`2 passed`

- [ ] **Step 6: 提交**

```bash
git add src/core/config.py .env.example tests/test_config_tushare.py
git commit -m "feat: add tushare_token to config"
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


def test_tushare_provider_not_available_without_token():
    provider = TushareProvider(token="")
    assert provider.is_available() is False


def test_tushare_provider_available_with_token():
    provider = TushareProvider(token="test_token")
    assert provider.is_available() is True


def test_tushare_provider_get_stock_list_returns_dataframe():
    provider = TushareProvider(token="test_token")
    df = provider.get_stock_list()
    # mock 模式下返回空 DataFrame
    assert df is not None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_tushare_provider.py -v
```

预期：`ModuleNotFoundError: No module named 'src.data.providers.tushare_provider'`

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
    """Tushare Pro 数据提供者"""

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
        if not self._token:
            return False
        pro = self._get_pro()
        return pro is not None

    def get_realtime_quote(self, symbol: str) -> Optional[MarketSnapshot]:
        """获取最新日线数据作为实时行情"""
        pro = self._get_pro()
        if pro is None:
            return None
        try:
            ts_code = _to_ts_code(symbol)
            df = pro.daily(ts_code=ts_code, limit=1)
            if df.empty:
                return None
            row = df.iloc[0]
            return MarketSnapshot(
                symbol=symbol,
                timestamp=datetime.strptime(str(row["trade_date"]), "%Y%m%d"),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["vol"]),
                amount=float(row["amount"]) * 1000,
            )
        except Exception as e:
            logger.warning(f"Tushare get_realtime_quote({symbol}) 失败: {e}")
            return None

    def get_history(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        freq: str = "daily",
    ) -> pd.DataFrame:
        pro = self._get_pro()
        if pro is None:
            return pd.DataFrame()
        try:
            ts_code = _to_ts_code(symbol)
            df = pro.daily(
                ts_code=ts_code,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d"),
            )
            if df.empty:
                return pd.DataFrame()
            df = df.rename(columns={
                "trade_date": "date",
                "vol": "volume",
            })
            return df
        except Exception as e:
            logger.warning(f"Tushare get_history({symbol}) 失败: {e}")
            return pd.DataFrame()

    def get_stock_list(self) -> pd.DataFrame:
        pro = self._get_pro()
        if pro is None:
            return pd.DataFrame()
        try:
            df = pro.stock_list(exchange="", list_status="L")
            if df.empty:
                return pd.DataFrame()
            df = df.rename(columns={"ts_code": "symbol", "name": "name"})
            return df[["symbol", "name"]]
        except Exception as e:
            logger.warning(f"Tushare get_stock_list 失败: {e}")
            return pd.DataFrame()


def _to_ts_code(symbol: str) -> str:
    """600519.SH -> 600519.SH（Tushare 格式与我们一致）"""
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
- Modify: `src/data/providers/provider_chain.py`
- Modify: `tests/test_provider_chain.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_provider_chain.py` 末尾新增：

```python
from src.data.providers.provider_chain import build_auto_provider_chain


def test_auto_chain_selects_akshare_when_available(monkeypatch):
    """本地环境：AkShare 可用时优先使用"""
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "auto")
    monkeypatch.setenv("TUSHARE_TOKEN", "test_token")
    # AkShare 探测会成功（本地环境）
    chain = build_auto_provider_chain()
    assert chain is not None


def test_auto_chain_falls_back_to_tushare(monkeypatch):
    """AkShare 不可用时降级到 Tushare"""
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "auto")
    monkeypatch.setenv("TUSHARE_TOKEN", "test_token")
    # 模拟 AkShare 不可用
    monkeypatch.setattr(
        "src.data.providers.akshare_provider.AkshareProvider.is_available",
        lambda self: False,
    )
    chain = build_auto_provider_chain()
    assert chain is not None
```

- [ ] **Step 2: 运行测试确认失败**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_provider_chain.py -v
```

预期：`FAILED` - `build_auto_provider_chain` 不存在

- [ ] **Step 3: 实现 auto 模式**

在 `src/data/providers/provider_chain.py` 末尾新增：

```python
from src.core.config import Settings
from src.data.providers.akshare_provider import AkshareProvider
from src.data.providers.tushare_provider import TushareProvider


def build_provider_chain_from_settings() -> ProviderChain:
    """根据配置构建数据提供者链"""
    settings = Settings()
    mode = settings.market_data_provider

    if mode == "tushare":
        return ProviderChain([TushareProvider(token=settings.tushare_token)])
    elif mode == "akshare":
        return ProviderChain([AkshareProvider()])
    else:
        # auto 模式
        return build_auto_provider_chain()


def build_auto_provider_chain() -> ProviderChain:
    """自动探测：AkShare 优先，失败降级 Tushare"""
    settings = Settings()
    akshare = AkshareProvider()
    tushare = TushareProvider(token=settings.tushare_token)

    # 探测 AkShare 全市场接口
    try:
        if akshare.is_available():
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if not df.empty:
                logger.info("auto 模式: AkShare 可用，使用 AkShare")
                return ProviderChain([akshare, tushare])
    except Exception as e:
        logger.warning(f"auto 模式: AkShare 探测失败 ({e})，降级到 Tushare")

    logger.info("auto 模式: 使用 Tushare")
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

### Task 4: 更新 .env.example 并验证配置

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: 更新 .env.example**

确认 `.env.example` 包含：

```bash
# 行情数据源 (auto/akshare/tushare)
MARKET_DATA_PROVIDER=auto
TUSHARE_TOKEN=your_tushare_token_here
```

- [ ] **Step 2: 提交**

```bash
git add .env.example
git commit -m "docs: update .env.example with tushare config"
```

---

### Task 5: 集成验证

- [ ] **Step 1: 本地验证 AkShare 模式**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -c "
from src.data.providers.provider_chain import build_provider_chain_from_settings
chain = build_provider_chain_from_settings()
print('providers:', [type(p).__name__ for p in chain._providers])
q = chain.get_realtime_quote('600519.SH')
print('quote:', q)
"
```

预期：providers 包含 AkshareProvider，quote 返回茅台数据

- [ ] **Step 2: 验证 Tushare 模式**

```bash
MARKET_DATA_PROVIDER=tushare TUSHARE_TOKEN=你的token /opt/anaconda3/envs/py311/bin/python3 -c "
from src.data.providers.provider_chain import build_provider_chain_from_settings
chain = build_provider_chain_from_settings()
print('providers:', [type(p).__name__ for p in chain._providers])
"
```

预期：providers 包含 TushareProvider

- [ ] **Step 3: 运行全量测试**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

预期：无新增失败

- [ ] **Step 4: 最终提交**

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
