# 全市场自动选股 + 丰富行情 Tab 实施计划

**Goal:** 新增全市场股票扫描功能（简化因子评分 + Top-10 选股），同时丰富"实时行情"Tab 展示更多腾讯行情字段（涨跌额、换手率、振幅、量比、市盈率）。

**Architecture:** 扩展 `_fetch_tencent_quotes` 提取更多腾讯行情字段，新增 `POST /api/v1/market/bulk` 批量行情端点。扫描器用简化因子评分（不依赖历史 K 线），仪表盘"今日选股"区域展示 Top-10 选股结果。

**Tech Stack:** Python 3.11, FastAPI, requests, akshare, pandas, pytest

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/data/providers/akshare_provider.py` | 修改 | 扩展 `_fetch_tencent_quotes` 字段，修复 `_build_catalog_frame` |
| `src/api/routes_market.py` | 修改 | 新增 `POST /api/v1/market/bulk` |
| `src/strategy/stock_scanner.py` | 新建 | `score_quote()` + `scan_market()` |
| `src/api/routes_dashboard.py` | 修改 | 新增 `POST /api/v1/dashboard/scan` |
| `tests/test_stock_scanner.py` | 新建 | 扫描器测试 |
| `tests/test_market_bulk_api.py` | 新建 | 批量行情 API 测试 |
| `src/api/dashboard.html` | 修改 | 丰富行情 Tab + 新增"今日选股"区域 |

---

### Task 1: 扩展腾讯行情字段 + 批量 API

**Files:**
- Modify: `src/data/providers/akshare_provider.py`
- Modify: `src/api/routes_market.py`
- Create: `tests/test_market_bulk_api.py`

- [ ] **Step 1: 扩展 `_TX_IDX` 字典**

```python
_TX_IDX = {
    "name": 1,
    "close": 3,
    "prev_close": 4,
    "open": 5,
    "volume": 6,
    "high": 33,
    "low": 34,
    "amount": 37,
    "change_pct": 32,   # 涨跌幅 %
    "turnover": 38,      # 换手率 %
    "amplitude": 43,     # 振幅 %
    "volume_ratio": 49,  # 量比
    "pe_ratio": 39,      # 市盈率
}
```

- [ ] **Step 2: 扩展 `_fetch_tencent_quotes` 返回更多字段**

在 `rows.append` 中添加：
```python
rows.append({
    "code": code,
    "symbol": sym,
    "name": fields[_TX_IDX["name"]],
    "close": fields[_TX_IDX["close"]],
    "prev_close": fields[_TX_IDX["prev_close"]],
    "open": fields[_TX_IDX["open"]],
    "high": fields[_TX_IDX["high"]],
    "low": fields[_TX_IDX["low"]],
    "volume": fields[_TX_IDX["volume"]],
    "amount": fields[_TX_IDX["amount"]],
    "change_pct": fields[_TX_IDX["change_pct"]],
    "turnover": fields[_TX_IDX["turnover"]],
    "amplitude": fields[_TX_IDX["amplitude"]],
    "volume_ratio": fields[_TX_IDX["volume_ratio"]],
    "pe_ratio": fields[_TX_IDX["pe_ratio"]],
})
```

- [ ] **Step 3: 新增 `_fetch_tencent_quotes_batch`**

```python
def _fetch_tencent_quotes_batch(symbols: list[str], batch_size: int = 200) -> pd.DataFrame:
    """分批拉取腾讯行情，支持全市场扫描。"""
    all_frames = []
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        df = _fetch_tencent_quotes(batch)
        if not df.empty:
            all_frames.append(df)
    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)
```

- [ ] **Step 4: 在 `routes_market.py` 新增 `POST /api/v1/market/bulk`**

```python
@router.post("/bulk")
def get_bulk_quotes(symbols: list[str]) -> list[dict]:
    """批量获取行情，支持 200+ 只股票。"""
    if not symbols:
        return []
    df = _fetch_tencent_quotes_batch(symbols[:500])
    if df.empty:
        return []
    return df.to_dict("records")
```

- [ ] **Step 5: 写测试 + 运行**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_market_bulk_api.py -v
```

- [ ] **Step 6: 提交**

---

### Task 2: 全市场扫描器

**Files:**
- Modify: `src/data/providers/akshare_provider.py` (修复 `_build_catalog_frame`)
- Create: `src/strategy/stock_scanner.py`
- Create: `tests/test_stock_scanner.py`

- [ ] **Step 1: 修复 `_build_catalog_frame`**

```python
def _build_catalog_frame() -> pd.DataFrame:
    """从三大交易所官网获取全市场 A 股列表（不走东方财富）。"""
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        return df[["code", "name"]]
    except Exception as e:
        logger.warning(f"_build_catalog_frame 失败: {e}")
        return pd.DataFrame(columns=["code", "name"])
```

- [ ] **Step 2: 创建 `src/strategy/stock_scanner.py`**

```python
from __future__ import annotations
from typing import Any


def score_quote(quote: dict[str, Any]) -> dict[str, Any]:
    """对单只股票的实时行情计算简化因子评分。

    因子: 涨跌幅(35%) + 振幅(25%) + 量比(20%) + 换手率(20%)
    """
    change_pct = _safe_float(quote.get("change_pct"))
    amplitude = _safe_float(quote.get("amplitude"))
    turnover = _safe_float(quote.get("turnover"))
    volume_ratio = _safe_float(quote.get("volume_ratio"))
    name = str(quote.get("name", ""))

    f_change = max(0, min(1, (change_pct + 5) / 15))
    f_amplitude = max(0, min(1, amplitude / 15))
    f_turnover = max(0, min(1, turnover / 20))
    f_volume_ratio = max(0, min(1, volume_ratio / 5))

    score = 0.35 * f_change + 0.25 * f_amplitude + 0.20 * f_volume_ratio + 0.20 * f_turnover

    if score >= 0.60 and change_pct > 0:
        action = "BUY"
    elif score <= 0.30 or change_pct < -3:
        action = "SELL"
    else:
        action = "HOLD"

    reasons = []
    if change_pct > 2:
        reasons.append(f"涨幅{change_pct:.1f}%，趋势向好")
    elif change_pct < -2:
        reasons.append(f"跌幅{change_pct:.1f}%，注意风险")
    if volume_ratio > 2:
        reasons.append(f"量比{volume_ratio:.1f}，资金活跃")
    if turnover > 5:
        reasons.append(f"换手{turnover:.1f}%，交投活跃")
    if amplitude > 8:
        reasons.append(f"振幅{amplitude:.1f}%，波动较大")
    if not reasons:
        reasons.append("指标平稳")

    return {
        "symbol": quote.get("symbol", ""),
        "name": name,
        "score": round(score, 4),
        "action": action,
        "reason": "、".join(reasons),
        "factors": {
            "change_pct": round(change_pct, 2),
            "amplitude": round(amplitude, 2),
            "turnover": round(turnover, 2),
            "volume_ratio": round(volume_ratio, 2),
        },
    }


def scan_market(stock_list, fetch_quotes_fn, top_n: int = 10) -> dict[str, Any]:
    """全市场扫描入口。"""
    symbols = [s["symbol"] for s in stock_list if s.get("symbol")]
    quotes_df = fetch_quotes_fn(symbols)
    if quotes_df.empty:
        return {"buy": [], "sell": [], "hold": [], "total_scanned": 0}

    results = [score_quote(row.to_dict()) for _, row in quotes_df.iterrows()]
    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "buy": [r for r in results if r["action"] == "BUY"][:top_n],
        "sell": [r for r in results if r["action"] == "SELL"][:top_n],
        "hold": [r for r in results if r["action"] == "HOLD"][:top_n],
        "total_scanned": len(results),
    }


def _safe_float(value) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
```

- [ ] **Step 3: 写测试 `tests/test_stock_scanner.py`**

```python
import pandas as pd
from src.strategy.stock_scanner import score_quote, scan_market


def test_score_quote_returns_buy_for_strong_stock():
    result = score_quote({
        "symbol": "300750.SZ", "name": "宁德时代",
        "change_pct": 2.56, "amplitude": 5.0, "turnover": 3.0, "volume_ratio": 2.5,
    })
    assert result["action"] == "BUY"
    assert result["score"] >= 0.60
    assert result["reason"]


def test_score_quote_returns_sell_for_declining_stock():
    result = score_quote({
        "symbol": "000001.SZ", "name": "平安银行",
        "change_pct": -4.76, "amplitude": 8.0, "turnover": 1.0, "volume_ratio": 0.5,
    })
    assert result["action"] == "SELL"


def test_score_quote_returns_hold_for_neutral_stock():
    result = score_quote({
        "symbol": "600519.SH", "name": "贵州茅台",
        "change_pct": -0.39, "amplitude": 2.0, "turnover": 0.37, "volume_ratio": 1.0,
    })
    assert result["action"] == "HOLD"


def test_scan_market_returns_grouped_results():
    mock_quotes = pd.DataFrame([
        {"symbol": "300750.SZ", "name": "宁德时代", "change_pct": 2.56, "amplitude": 5.0, "turnover": 3.0, "volume_ratio": 2.5},
        {"symbol": "600519.SH", "name": "贵州茅台", "change_pct": -0.39, "amplitude": 2.0, "turnover": 0.37, "volume_ratio": 1.0},
    ])
    result = scan_market(
        [{"symbol": "300750.SZ"}, {"symbol": "600519.SH"}],
        lambda syms: mock_quotes,
    )
    assert result["total_scanned"] == 2
    assert len(result["buy"]) == 1
    assert result["buy"][0]["symbol"] == "300750.SZ"
```

- [ ] **Step 4: 运行测试**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_stock_scanner.py -v
```

- [ ] **Step 5: 提交**

---

### Task 3: 扫描 API 端点

**Files:**
- Modify: `src/api/routes_dashboard.py`

- [ ] **Step 1: 新增 `POST /api/v1/dashboard/scan`**

```python
@router.post("/api/v1/dashboard/scan")
def scan_stock_pool(config: dict | None = None) -> dict:
    """全市场自动选股，返回 Top-N 及选股理由。"""
    from src.strategy.stock_scanner import scan_market, _fetch_tencent_quotes_batch

    cfg = config or {}
    top_n = int(cfg.get("top_n", 10))

    provider = AkshareProvider()
    stock_list_df = provider.get_stock_list()
    stock_list = stock_list_df.to_dict("records")

    if not stock_list:
        return {"status": "no_catalog", "buy": [], "sell": [], "hold": [], "total_scanned": 0}

    result = scan_market(
        stock_list=stock_list,
        fetch_quotes_fn=lambda syms: _fetch_tencent_quotes_batch(syms),
        top_n=top_n,
    )
    return {"status": "ok", **result}
```

- [ ] **Step 2: 运行测试确认不报错**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/ --ignore=tests/test_dashboard_api.py -q
```

- [ ] **Step 3: 提交**

---

### Task 4: 仪表盘 UI — 丰富行情 Tab + 今日选股

**Files:**
- Modify: `src/api/dashboard.html`

- [ ] **Step 1: 扩展行情 Tab 表头**

```html
<th>时间</th><th>股票</th><th>最新价</th><th>涨跌额</th>
<th>涨跌幅</th><th>今开</th><th>最高</th><th>最低</th>
<th>成交量</th><th>换手率</th><th>振幅</th><th>量比</th>
```

- [ ] **Step 2: 更新 `renderMarketQuotes` 函数**

- [ ] **Step 3: 更新 `refreshMarketQuotes` 使用批量 API**

- [ ] **Step 4: 添加"今日选股"区域到 panel-center**

- [ ] **Step 5: 添加 CSS + JavaScript**

- [ ] **Step 6: 提交**

---

## Acceptance Criteria

- `POST /api/v1/market/bulk` 返回包含换手率、振幅、量比等字段的批量行情
- "实时行情"Tab 展示 12 列数据（时间、股票、最新价、涨跌额、涨跌幅、今开、最高、最低、成交量、换手率、振幅、量比）
- `POST /api/v1/dashboard/scan` 返回全市场扫描结果（buy/sell/hold 三组，每组 Top-10）
- 仪表盘"今日选股"区域可触发扫描，结果以排名表格展示
- 扫描耗时 < 15 秒
- 现有测试不被破坏
