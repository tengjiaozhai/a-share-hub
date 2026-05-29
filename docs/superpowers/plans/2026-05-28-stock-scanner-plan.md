# 全市场自动选股 实施计划

**Goal:** 新增全市场股票扫描功能，用腾讯实时行情的简化因子（涨跌幅、振幅、换手率、量比等）评分排序，返回 Top-10 及选股理由。

**Architecture:** 用 `akshare.stock_info_a_code_name()`（走三大交易所官网，不走东方财富）获取全市场 ~5500 只股票列表。分批调用腾讯 `qt.gtimg.cn` 批量行情（200 只/批，~5s 完成全扫描）。用实时行情字段（涨跌幅、振幅、换手率、量比）计算简化因子评分，排序取 Top-10 并生成中文理由。

**Tech Stack:** Python 3.11, FastAPI, requests, akshare, pandas, pytest

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/data/providers/akshare_provider.py` | 修改 | 修复 `_build_catalog_frame`，新增 `_fetch_tencent_quotes_batch` |
| `src/strategy/stock_scanner.py` | 新建 | `score_quote()` 简化因子评分 + `scan_market()` 全市场扫描 |
| `src/api/routes_dashboard.py` | 修改 | 新增 `POST /api/v1/dashboard/scan` |
| `tests/test_stock_scanner.py` | 新建 | 评分和扫描测试 |
| `src/api/dashboard.html` | 修改 | 新增"今日选股"区域 |

---

### Task 1: 修复股票列表 + 全市场扫描器

**Files:**
- Modify: `src/data/providers/akshare_provider.py`
- Create: `src/strategy/stock_scanner.py`
- Create: `tests/test_stock_scanner.py`

- [ ] **Step 1: 修复 `_build_catalog_frame`**

将 `akshare_provider.py` 中的 `_build_catalog_frame()` 从返回空改为调用 akshare：

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

- [ ] **Step 2: 新增 `_fetch_tencent_quotes_batch`**

在 `akshare_provider.py` 中新增分批拉取函数：

```python
def _fetch_tencent_quotes_batch(symbols: list[str], batch_size: int = 200) -> pd.DataFrame:
    """分批拉取腾讯行情，支持全市场扫描。

    symbols: ['600519.SH', '000858.SZ', ...]
    batch_size: 每批数量，默认 200

    返回含所有 symbol 行情的 DataFrame。
    """
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

同时更新 `_fetch_tencent_quotes` 提取更多字段（涨跌幅、振幅、换手率、量比）：

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
}
```

在 `_fetch_tencent_quotes` 的 rows.append 中添加这些字段。

- [ ] **Step 3: 创建 `src/strategy/stock_scanner.py`**

```python
from __future__ import annotations
from typing import Any


def score_quote(quote: dict[str, Any]) -> dict[str, Any]:
    """对单只股票的实时行情计算简化因子评分。

    输入: 腾讯行情 dict，含 change_pct, amplitude, turnover, volume_ratio, close, prev_close
    输出: {"symbol", "score", "action", "reason", "factors"}
    """
    change_pct = float(quote.get("change_pct", 0) or 0)
    amplitude = float(quote.get("amplitude", 0) or 0)
    turnover = float(quote.get("turnover", 0) or 0)
    volume_ratio = float(quote.get("volume_ratio", 1) or 1)
    close = float(quote.get("close", 0) or 0)
    prev_close = float(quote.get("prev_close", 0) or 0)
    name = quote.get("name", "")

    # 简化因子评分（0-1 归一化）
    # 涨跌幅：正向，[-5, 10] 映射到 [0, 1]
    f_change = max(0, min(1, (change_pct + 5) / 15))
    # 振幅：中性偏好，[0, 15] 映射到 [0, 1]
    f_amplitude = max(0, min(1, amplitude / 15))
    # 换手率：活跃偏好，[0, 20] 映射到 [0, 1]
    f_turnover = max(0, min(1, turnover / 20))
    # 量比：放量偏好，[0, 5] 映射到 [0, 1]
    f_volume_ratio = max(0, min(1, volume_ratio / 5))

    # 加权评分
    score = (
        0.35 * f_change
        + 0.25 * f_amplitude
        + 0.20 * f_volume_ratio
        + 0.20 * f_turnover
    )

    # 信号判断
    if score >= 0.60 and change_pct > 0:
        action = "BUY"
    elif score <= 0.30 or change_pct < -3:
        action = "SELL"
    else:
        action = "HOLD"

    # 生成理由
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


def scan_market(
    stock_list: list[dict[str, str]],
    fetch_quotes_fn,
    top_n: int = 10,
) -> dict[str, Any]:
    """全市场扫描入口。

    stock_list: [{"symbol": "600519.SH", "name": "贵州茅台"}, ...]
    fetch_quotes_fn: callable(symbols: list[str]) -> DataFrame
    top_n: 返回前 N 只

    返回: {"buy": [...], "sell": [...], "hold": [...], "total_scanned": N}
    """
    symbols = [s["symbol"] for s in stock_list if s.get("symbol")]
    quotes_df = fetch_quotes_fn(symbols)

    if quotes_df.empty:
        return {"buy": [], "sell": [], "hold": [], "total_scanned": 0}

    results = []
    for _, row in quotes_df.iterrows():
        quote = row.to_dict()
        result = score_quote(quote)
        results.append(result)

    # 按评分降序排序
    results.sort(key=lambda x: x["score"], reverse=True)

    buy = [r for r in results if r["action"] == "BUY"]
    sell = [r for r in results if r["action"] == "SELL"]
    hold = [r for r in results if r["action"] == "HOLD"]

    return {
        "buy": buy[:top_n],
        "sell": sell[:top_n],
        "hold": hold[:top_n],
        "total_scanned": len(results),
    }
```

- [ ] **Step 4: 写测试 `tests/test_stock_scanner.py`**

```python
from src.strategy.stock_scanner import score_quote, scan_market


def test_score_quote_returns_buy_for_strong_stock():
    quote = {
        "symbol": "300750.SZ", "name": "宁德时代",
        "close": 200.0, "prev_close": 195.0,
        "change_pct": 2.56, "amplitude": 5.0,
        "turnover": 3.0, "volume_ratio": 2.5,
    }
    result = score_quote(quote)
    assert result["action"] == "BUY"
    assert result["score"] >= 0.60
    assert "symbol" in result
    assert "reason" in result
    assert "factors" in result


def test_score_quote_returns_sell_for_declining_stock():
    quote = {
        "symbol": "000001.SZ", "name": "平安银行",
        "close": 10.0, "prev_close": 10.5,
        "change_pct": -4.76, "amplitude": 8.0,
        "turnover": 1.0, "volume_ratio": 0.5,
    }
    result = score_quote(quote)
    assert result["action"] == "SELL"


def test_score_quote_returns_hold_for_neutral_stock():
    quote = {
        "symbol": "600519.SH", "name": "贵州茅台",
        "close": 1275.0, "prev_close": 1280.0,
        "change_pct": -0.39, "amplitude": 2.0,
        "turnover": 0.37, "volume_ratio": 1.0,
    }
    result = score_quote(quote)
    assert result["action"] == "HOLD"


def test_scan_market_returns_grouped_results():
    mock_list = [
        {"symbol": "300750.SZ", "name": "宁德时代"},
        {"symbol": "600519.SH", "name": "贵州茅台"},
    ]
    import pandas as pd
    mock_quotes = pd.DataFrame([
        {"symbol": "300750.SZ", "name": "宁德时代", "close": 200.0, "prev_close": 195.0,
         "change_pct": 2.56, "amplitude": 5.0, "turnover": 3.0, "volume_ratio": 2.5},
        {"symbol": "600519.SH", "name": "贵州茅台", "close": 1275.0, "prev_close": 1280.0,
         "change_pct": -0.39, "amplitude": 2.0, "turnover": 0.37, "volume_ratio": 1.0},
    ])

    result = scan_market(mock_list, lambda symbols: mock_quotes, top_n=10)

    assert result["total_scanned"] == 2
    assert isinstance(result["buy"], list)
    assert isinstance(result["sell"], list)
    assert isinstance(result["hold"], list)
```

- [ ] **Step 5: 运行测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_stock_scanner.py -v
```

- [ ] **Step 6: 提交**

```bash
git add src/data/providers/akshare_provider.py src/strategy/stock_scanner.py tests/test_stock_scanner.py
git commit -m "feat: add full-market stock scanner with simplified factor scoring"
```

---

### Task 2: 扫描 API 端点

**Files:**
- Modify: `src/api/routes_dashboard.py`

- [ ] **Step 1: 新增 `POST /api/v1/dashboard/scan`**

在 `routes_dashboard.py` 末尾添加：

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

```bash
git add src/api/routes_dashboard.py
git commit -m "feat: add scan API endpoint at /api/v1/dashboard/scan"
```

---

### Task 3: 仪表盘"今日选股"UI

**Files:**
- Modify: `src/api/dashboard.html`

- [ ] **Step 1: 在 panel-center 添加"今日选股"区域**

在 `<h2>本轮运行</h2>` 之前插入：

```html
<h2>今日选股</h2>
<div class="scan-card" id="scan-result">
  <button class="run-btn" id="scan-btn" onclick="triggerScan()" style="margin-bottom:10px">全市场扫描</button>
  <div id="scan-content" style="font-size:12px;color:var(--dim)">点击按钮开始扫描</div>
</div>
```

- [ ] **Step 2: 添加 CSS**

```css
/* ── STOCK SCANNER ── */
.scan-card{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-lg);padding:12px;margin-bottom:12px}
.scan-table{width:100%;border-collapse:collapse}
.scan-table th{padding:6px 8px;text-align:left;font-size:11px;color:var(--dim);font-weight:500;text-transform:uppercase;border-bottom:1px solid var(--border)}
.scan-table td{padding:6px 8px;font-size:12px;border-bottom:1px solid var(--border)}
.scan-table tr:hover{background:rgba(96,165,250,.05)}
.scan-badge{padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700}
.scan-badge.buy{background:rgba(34,197,94,.2);color:var(--green)}
.scan-badge.sell{background:rgba(239,68,68,.2);color:var(--red)}
.scan-badge.hold{background:rgba(148,163,184,.15);color:var(--muted)}
.scan-section-title{font-size:12px;color:var(--muted);margin:10px 0 6px;font-weight:600}
.scan-summary{font-size:11px;color:var(--dim);margin-bottom:8px}
```

- [ ] **Step: 添加 JavaScript**

```javascript
const SCAN_API = '/api/v1/dashboard/scan';
let scanRunning = false;

async function triggerScan() {
  if (scanRunning) return;
  scanRunning = true;
  const btn = document.getElementById('scan-btn');
  btn.disabled = true;
  btn.textContent = '扫描中...';
  document.getElementById('scan-content').innerHTML = '<span style="color:var(--yellow)">正在扫描全市场，请稍候（约 5-10 秒）...</span>';

  try {
    const res = await fetch(SCAN_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ top_n: 10 }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || '扫描失败');
    renderScanResult(body);
  } catch (e) {
    document.getElementById('scan-content').innerHTML = `<span style="color:var(--red)">扫描失败: ${escapeHtml(e.message)}</span>`;
  } finally {
    scanRunning = false;
    btn.disabled = false;
    btn.textContent = '全市场扫描';
  }
}

function renderScanResult(data) {
  const area = document.getElementById('scan-content');
  if (data.status === 'no_catalog') {
    area.innerHTML = '<span style="color:var(--yellow)">股票列表不可用，请检查网络</span>';
    return;
  }

  let html = `<div class="scan-summary">已扫描 ${data.total_scanned} 只股票</div>`;

  const sections = [
    { key: 'buy', label: '买入信号', cls: 'buy' },
    { key: 'hold', label: '持有信号', cls: 'hold' },
    { key: 'sell', label: '卖出信号', cls: 'sell' },
  ];

  for (const sec of sections) {
    const items = data[sec.key] || [];
    if (!items.length) continue;
    html += `<div class="scan-section-title">${sec.label} (${items.length})</div>`;
    html += '<table class="scan-table"><thead><tr>';
    html += '<th>排名</th><th>股票</th><th>动作</th><th>评分</th><th>核心原因</th>';
    html += '</tr></thead><tbody>';
    items.forEach((item, idx) => {
      html += `<tr>
        <td>${idx + 1}</td>
        <td>${escapeHtml(item.symbol)} ${escapeHtml(item.name || '')}</td>
        <td><span class="scan-badge ${sec.cls}">${escapeHtml(item.action)}</span></td>
        <td style="font-weight:600">${item.score.toFixed(4)}</td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(item.reason)}">${escapeHtml(item.reason)}</td>
      </tr>`;
    });
    html += '</tbody></table>';
  }

  area.innerHTML = html;
}
```

- [ ] **Step 4: 浏览器验证**

```bash
pkill -f "uvicorn src.main" 2>/dev/null; sleep 1
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 3
# 用 Playwright 截图验证
```

- [ ] **Step 5: 提交**

```bash
git add src/api/dashboard.html
git commit -m "feat: add stock pool scanner UI to dashboard"
```

---

## Acceptance Criteria

- `POST /api/v1/dashboard/scan` 返回全市场扫描结果，包含 buy/sell/hold 三组
- 每只股票有 symbol, name, score, action, reason, factors
- Top-10 按评分降序排列
- 仪表盘"今日选股"区域可触发扫描，结果以表格展示
- 扫描耗时 < 15 秒
- 现有 142+ 测试不被破坏

## Self-Review

- Spec coverage：全市场扫描、简化因子评分、Top-10、买卖持有信号、选股理由、仪表盘 UI
- Placeholder scan：无 TODO/TBD
- Type consistency：`score_quote` 返回结构与 `renderScanResult` 消费的字段一致
