# 腾讯历史 K 线 + 仪表盘快速回测 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把东方财富历史 K 线替换为腾讯财经接口，修复 `get_history()`，并在仪表盘新增"快速回测"独立区域。

**Architecture:** 用腾讯 `web.ifzq.gtimg.cn` 的 K 线接口替换东方财富 `push2his.eastmoney.com`。`get_history()` 从腾讯获取日线数据，回测引擎 `run_daily_backtest()` 消费这些数据。仪表盘 panel-left 底部新增"快速回测"表单，调用新增的 `/api/v1/dashboard/backtest` API。

**Tech Stack:** Python 3.11, FastAPI, requests, pandas, pytest

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/data/providers/akshare_provider.py` | 修改 | 新增 `_fetch_tencent_kline()`，重写 `get_history()` |
| `tests/test_akshare_history.py` | 新建 | 测试腾讯 K 线获取和 `get_history()` |
| `src/api/routes_dashboard.py` | 修改 | 新增 `POST /api/v1/dashboard/backtest` |
| `tests/test_backtest_api.py` | 新建 | 测试回测 API 端点 |
| `src/main.py` | 修改 | CLI `backtest` 命令实际调用 engine |
| `src/api/dashboard.html` | 修改 | panel-left 新增"快速回测"区域 |

---

### Task 1: 腾讯历史 K 线接口

**Files:**
- Modify: `src/data/providers/akshare_provider.py`
- Create: `tests/test_akshare_history.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_akshare_history.py
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.data.providers.akshare_provider import _fetch_tencent_kline, AkshareProvider


_FAKE_RESPONSE = '''{
  "code": 0,
  "data": {
    "sh600519": {
      "qfqday": [
        ["2025-01-02", "1472.443", "1436.443", "1472.933", "1428.443", "50029.000"],
        ["2025-01-03", "1442.943", "1423.443", "1443.433", "1415.453", "32628.000"]
      ]
    }
  }
}'''


def test_fetch_tencent_kline_parses_response():
    mock_resp = MagicMock()
    mock_resp.text = _FAKE_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("src.data.providers.akshare_provider.requests.get", return_value=mock_resp):
        df = _fetch_tencent_kline("sh600519", "2025-01-01", "2025-01-31")

    assert len(df) == 2
    assert list(df.columns) == ["date", "open", "close", "high", "low", "volume"]
    assert df.iloc[0]["date"] == "2025-01-02"
    assert df.iloc[0]["close"] == 1436.443
    assert df.iloc[1]["volume"] == 32628


def test_fetch_tencent_kline_returns_empty_on_no_data():
    mock_resp = MagicMock()
    mock_resp.text = '{"code":0,"data":{"sh999999":{}}}'
    mock_resp.raise_for_status = MagicMock()

    with patch("src.data.providers.akshare_provider.requests.get", return_value=mock_resp):
        df = _fetch_tencent_kline("sh999999", "2025-01-01", "2025-01-31")

    assert df.empty


def test_fetch_tencent_kline_returns_empty_on_network_error():
    with patch("src.data.providers.akshare_provider.requests.get", side_effect=Exception("timeout")):
        df = _fetch_tencent_kline("sh600519", "2025-01-01", "2025-01-31")

    assert df.empty


def test_akshare_provider_get_history_returns_dataframe():
    mock_resp = MagicMock()
    mock_resp.text = _FAKE_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    provider = AkshareProvider()
    with patch("src.data.providers.akshare_provider.requests.get", return_value=mock_resp):
        df = provider.get_history("600519.SH", datetime(2025, 1, 1), datetime(2025, 1, 31))

    assert not df.empty
    assert "date" in df.columns
    assert "close" in df.columns
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_akshare_history.py -v 2>&1 | tail -15
```

预期：`_fetch_tencent_kline` 不存在 → FAIL

- [ ] **Step 3: 实现**

在 `akshare_provider.py` 中，在 `_fetch_tencent_quotes` 函数之后新增：

```python
_KLINE_FREQ_MAP = {"daily": "day", "weekly": "week", "monthly": "month"}


def _fetch_tencent_kline(tx_code: str, start_date: str, end_date: str, freq: str = "day") -> pd.DataFrame:
    """腾讯历史 K 线。

    tx_code: 腾讯格式代码，如 'sh600519'
    start_date / end_date: 'YYYY-MM-DD'
    freq: 'day' / 'week' / 'month'

    返回 columns: [date, open, close, high, low, volume]
    """
    try:
        url = (
            f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?param={tx_code},{freq},{start_date},{end_date},1000,qfq"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            return pd.DataFrame()

        stock_data = data.get("data", {})
        if not stock_data:
            return pd.DataFrame()

        kline_key = f"qfq{freq}" if freq != "month" else "qfqmonth"
        rows = []
        for key, val in stock_data.items():
            kline = val.get(kline_key, val.get(f"qfq{freq}", []))
            if not kline:
                continue
            for row in kline:
                if len(row) >= 6:
                    rows.append({
                        "date": row[0],
                        "open": float(row[1]),
                        "close": float(row[2]),
                        "high": float(row[3]),
                        "low": float(row[4]),
                        "volume": int(float(row[5])),
                    })

        return pd.DataFrame(rows)
    except Exception as e:
        logger.warning(f"_fetch_tencent_kline({tx_code}) 失败: {e}")
        return pd.DataFrame()
```

然后重写 `get_history` 方法：

```python
    def get_history(self, symbol: str, start_date: datetime, end_date: datetime, freq: str = "daily") -> pd.DataFrame:
        """获取历史 K 线数据（腾讯财经接口）。"""
        try:
            normalized = normalize_symbol(symbol)
        except ValueError:
            return pd.DataFrame()

        code, exchange = normalized.split(".")
        tx_code = f"{_TX_EXCHANGE_MAP.get(exchange, 'sh')}{code}"
        tx_freq = _KLINE_FREQ_MAP.get(freq, "day")
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        return _fetch_tencent_kline(tx_code, start_str, end_str, tx_freq)
```

更新类的 docstring（移除"历史 K 线：暂缓"）：

```python
class AkshareProvider(DataProvider):
    """AkShare 行情数据提供者。

    行情快照：腾讯 qt.gtimg.cn
    历史 K 线：腾讯 web.ifzq.gtimg.cn
    """
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_akshare_history.py -v 2>&1 | tail -15
```

- [ ] **Step 5: 手动验证真实数据**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -c "
from src.data.providers.akshare_provider import AkshareProvider
from datetime import datetime
p = AkshareProvider()
df = p.get_history('600519.SH', datetime(2025,1,1), datetime(2025,3,31))
print(df.head(3))
print(f'total rows: {len(df)}')
"
```

预期：返回非空 DataFrame，含 date/open/close/high/low/volume

- [ ] **Step 6: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/data/providers/akshare_provider.py tests/test_akshare_history.py
git commit -m "feat: replace eastmoney kline with tencent finance API"
```

---

### Task 2: 回测 API 端点

**Files:**
- Modify: `src/api/routes_dashboard.py`
- Create: `tests/test_backtest_api.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_backtest_api.py
from fastapi.testclient import TestClient
from src.main import build_app


def test_backtest_endpoint_returns_metrics(monkeypatch):
    from src.api import routes_dashboard

    mock_bars = [
        {"date": "2025-01-02", "open": 100.0, "close": 102.0, "high": 103.0, "low": 99.0, "volume": 1000},
        {"date": "2025-01-03", "open": 102.0, "close": 104.0, "high": 105.0, "low": 101.0, "volume": 1200},
    ]

    def mock_get_history(symbol, start_date, end_date, freq="daily"):
        import pandas as pd
        return pd.DataFrame(mock_bars)

    from src.data.providers.akshare_provider import AkshareProvider
    monkeypatch.setattr(AkshareProvider, "get_history", mock_get_history)

    client = TestClient(build_app())
    response = client.post("/api/v1/dashboard/backtest", json={
        "watchlist": ["600519.SH"],
        "start_date": "2025-01-01",
        "end_date": "2025-03-31",
        "capital_base": 1000000,
    })

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert len(data["results"]) == 1
    assert "metrics" in data["results"][0]
    assert "total_return" in data["results"][0]["metrics"]


def test_backtest_endpoint_returns_400_for_empty_watchlist():
    client = TestClient(build_app())
    response = client.post("/api/v1/dashboard/backtest", json={
        "watchlist": [],
        "start_date": "2025-01-01",
        "end_date": "2025-03-31",
        "capital_base": 1000000,
    })
    assert response.status_code == 400
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_backtest_api.py -v 2>&1 | tail -15
```

预期：`/api/v1/dashboard/backtest` 不存在 → 404/405

- [ ] **Step 3: 实现**

在 `routes_dashboard.py` 中新增 backtest 端点。在文件末尾（`router` 定义之后）添加：

```python
@router.post("/api/v1/dashboard/backtest")
def run_backtest(config: dict) -> dict:
    watchlist = config.get("watchlist") or ["600519.SH"]
    start_str = config.get("start_date", "2025-01-01")
    end_str = config.get("end_date", "2025-03-31")
    capital_base = int(config.get("capital_base", 1_000_000))

    if not watchlist:
        raise HTTPException(status_code=400, detail="watchlist is empty")

    from datetime import datetime
    from src.backtest.engine import run_daily_backtest
    from src.backtest.metrics import calculate_metrics
    from src.data.providers.akshare_provider import AkshareProvider
    from src.indicators.technical_indicators import compute_feature_row
    from src.strategy.signal_engine import build_signal
    from src.strategy.strategy_config import StrategyConfig
    from src.core.config import Settings

    settings = Settings()
    strategy_config = StrategyConfig.from_settings(settings)
    provider = AkshareProvider()

    start_date = datetime.strptime(start_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_str, "%Y-%m-%d")

    results = []
    for symbol in watchlist:
        bars_df = provider.get_history(symbol, start_date, end_date)
        if bars_df.empty:
            continue

        bars = bars_df.to_dict("records")
        close_prices = [b["close"] for b in bars]

        signals = []
        for i in range(60, len(bars)):
            window = close_prices[max(0, i - 60):i + 1]
            features = compute_feature_row(window)
            signal = build_signal(symbol, features, strategy_config)
            if signal["action"] != "HOLD":
                signals.append({
                    "date": bars[i]["date"],
                    "action": signal["action"],
                    "target_position_ratio": settings.strategy_max_position_ratio if signal["action"] == "BUY" else 0.0,
                })

        bt_result = run_daily_backtest(
            symbol=symbol,
            bars=bars,
            initial_cash=float(capital_base),
            signals=signals,
        )
        metrics = calculate_metrics(bt_result["equity_curve"], bt_result["trades"])

        results.append({
            "symbol": symbol,
            "metrics": metrics,
            "trade_count": len(bt_result["trades"]),
            "final_nav": bt_result["final_nav"],
        })

    if not results:
        return {"status": "no_data", "results": [], "summary": {}}

    avg_return = sum(r["metrics"]["total_return"] for r in results) / len(results)
    worst_dd = min(r["metrics"]["max_drawdown"] for r in results)
    total_trades = sum(r["trade_count"] for r in results)

    return {
        "status": "ok",
        "start_date": start_str,
        "end_date": end_str,
        "results": results,
        "summary": {
            "total_return_avg": round(avg_return, 6),
            "max_drawdown_worst": round(worst_dd, 6),
            "total_trades": total_trades,
        },
    }
```

注意：需要在文件顶部确认已导入 `HTTPException`。

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_backtest_api.py -v 2>&1 | tail -15
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/routes_dashboard.py tests/test_backtest_api.py
git commit -m "feat: add backtest API endpoint at /api/v1/dashboard/backtest"
```

---

### Task 3: 仪表盘"快速回测"UI

**Files:**
- Modify: `src/api/dashboard.html`

- [ ] **Step 1: 在 panel-left 的 run-btn 按钮之后添加回测区域**

在 `</div>`（关闭 panel-left）之前插入：

```html
    <h2 style="margin-top:12px;border-top:1px solid var(--border);padding-top:14px">快速回测</h2>
    <div class="field-row">
      <div class="field">
        <label>开始日期</label>
        <input type="date" id="cfg-bt-start" value="2025-01-01">
      </div>
      <div class="field">
        <label>结束日期</label>
        <input type="date" id="cfg-bt-end" value="2025-03-31">
      </div>
    </div>
    <button class="run-btn" id="bt-btn" onclick="triggerBacktest()">运行回测</button>
    <div id="bt-result" style="margin-top:8px;font-size:12px;color:var(--muted)"></div>
```

- [ ] **Step 2: 添加回测 CSS 样式**

在 `/* ── BADGES ── */` 之前添加：

```css
/* ── BACKTEST RESULT CARD ── */
.bt-card{
  background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);
  padding:10px;margin-top:6px;font-size:12px;
}
.bt-card .bt-row{display:flex;justify-content:space-between;padding:3px 0}
.bt-card .bt-label{color:var(--dim)}
.bt-card .bt-value{color:var(--fg);font-weight:600}
.bt-card .bt-value.green{color:var(--green)}.bt-card .bt-value.red{color:var(--red)}
```

- [ ] **Step 3: 添加回测 JavaScript**

在 `async function triggerRun()` 之前添加：

```javascript
const BACKTEST_API = '/api/v1/dashboard/backtest';
let btRunning = false;

async function triggerBacktest() {
  if (btRunning) return;
  const watchlist = document.getElementById('cfg-watchlist').value
    .split(',').map(s => s.trim()).filter(Boolean);
  if (!watchlist.length) { alert('请先填写观察列表'); return; }

  btRunning = true;
  const btn = document.getElementById('bt-btn');
  btn.disabled = true;
  btn.textContent = '回测中...';
  document.getElementById('bt-result').innerHTML = '<span style="color:var(--yellow)">正在计算，请稍候...</span>';

  try {
    const res = await fetch(BACKTEST_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        watchlist,
        start_date: document.getElementById('cfg-bt-start').value,
        end_date: document.getElementById('cfg-bt-end').value,
        capital_base: Number(document.getElementById('cfg-capital').value),
      }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || '回测失败');
    renderBacktestResult(body);
  } catch (e) {
    document.getElementById('bt-result').innerHTML = `<span style="color:var(--red)">回测失败: ${escapeHtml(e.message)}</span>`;
  } finally {
    btRunning = false;
    btn.disabled = false;
    btn.textContent = '运行回测';
  }
}

function renderBacktestResult(data) {
  const area = document.getElementById('bt-result');
  if (data.status === 'no_data' || !data.results.length) {
    area.innerHTML = '<span style="color:var(--yellow)">无历史数据，无法回测</span>';
    return;
  }
  const s = data.summary;
  const avgRet = (s.total_return_avg * 100).toFixed(2);
  const worstDd = (s.max_drawdown_worst * 100).toFixed(2);
  const retCls = s.total_return_avg >= 0 ? 'green' : 'red';

  let rows = `<div class="bt-card">
    <div class="bt-row"><span class="bt-label">区间平均收益</span><span class="bt-value ${retCls}">${avgRet}%</span></div>
    <div class="bt-row"><span class="bt-label">最大回撤</span><span class="bt-value red">${worstDd}%</span></div>
    <div class="bt-row"><span class="bt-label">总交易次数</span><span class="bt-value">${s.total_trades}</span></div>`;

  for (const r of data.results) {
    const ret = (r.metrics.total_return * 100).toFixed(2);
    const dd = (r.metrics.max_drawdown * 100).toFixed(2);
    rows += `<div style="border-top:1px solid var(--border);margin-top:6px;padding-top:6px">
      <div class="bt-row"><span class="bt-label">${escapeHtml(r.symbol)}</span><span class="bt-value ${Number(ret)>=0?'green':'red'}">${ret}%</span></div>
      <div class="bt-row"><span class="bt-label">  回撤</span><span class="bt-value red">${dd}%</span></div>
      <div class="bt-row"><span class="bt-label">  交易</span><span class="bt-value">${r.trade_count}笔</span></div>
    </div>`;
  }
  rows += '</div>';
  area.innerHTML = rows;
}
```

- [ ] **Step 4: 浏览器验证**

重启服务后访问 `http://localhost:8000/dashboard`，确认：
1. "快速回测"区域出现在策略配置面板底部
2. 日期输入框可操作
3. 点击"运行回测"后显示结果卡片

```bash
pkill -f "uvicorn src.main" 2>/dev/null; sleep 1
cd /Users/shenmingjie/workSpace/tranding/a-share-hub && /opt/anaconda3/envs/py311/bin/python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
sleep 3
curl -s http://localhost:8000/health
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/dashboard.html
git commit -m "feat: add quick backtest section to dashboard"
```

---

## Acceptance Criteria

- `AkshareProvider.get_history()` 返回真实腾讯 K 线数据，不再返回空 DataFrame
- `POST /api/v1/dashboard/backtest` 返回回测指标（total_return, max_drawdown, turnover）
- 仪表盘 panel-left 底部有"快速回测"区域，含日期输入和运行按钮
- 回测结果以卡片形式展示，含收益、回撤、交易次数
- 现有测试不被破坏

## Self-Review

- Spec coverage：覆盖了腾讯 K 线替换、回测 API、仪表盘 UI 三部分
- Placeholder scan：无 TODO/TBD
- Type consistency：`_fetch_tencent_kline` 返回 DataFrame columns 与 `run_daily_backtest` 的 bars 格式对齐（date, close）
