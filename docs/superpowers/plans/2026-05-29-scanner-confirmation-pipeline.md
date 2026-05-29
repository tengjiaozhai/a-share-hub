# 扫描器预筛 + 回测确认 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把扫描器（短线因子）和回测（长线因子）联动，扫描器先筛 Top-N 候选，回测逐只确认，只展示两边都同意 BUY 的股票。

**Architecture:** 扫描器用实时因子（涨跌幅/振幅/量比/换手率）做第一轮筛选，取 Top-N BUY 候选。对每只候选拉取 60 天 K 线，用 `build_signal()` 做第二轮确认。最终结果标注"已确认"/"未确认"。

**Tech Stack:** Python 3.11, FastAPI, pandas, pytest

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/strategy/stock_scanner.py` | 修改 | 新增 `confirm_buy_candidates()` |
| `src/api/routes_dashboard.py` | 修改 | scan 端点接入确认逻辑 |
| `tests/test_stock_scanner.py` | 修改 | 新增确认逻辑测试 |
| `src/api/dashboard.html` | 修改 | 扫描结果展示"已确认"标记 |

---

### Task 1: 扫描器确认逻辑

**Files:**
- Modify: `src/strategy/stock_scanner.py`
- Modify: `tests/test_stock_scanner.py`

- [ ] **Step 1: 写失败测试**

```python
def test_confirm_buy_candidates_filters_holds():
    from src.strategy.strategy_config import StrategyConfig
    config = StrategyConfig(top_n=10, max_position_ratio=0.2, buy_score_threshold=0.55, sell_score_threshold=-0.20)

    # 模拟扫描器输出的 BUY 候选
    candidates = [
        {"symbol": "300750.SZ", "name": "宁德时代", "score": 0.68, "action": "BUY", "reason": "涨幅6%"},
        {"symbol": "000001.SZ", "name": "平安银行", "score": 0.60, "action": "BUY", "reason": "涨幅3%"},
    ]

    # 模拟 K 线数据：300750 趋势强（确认），000001 趋势弱（不确认）
    import pandas as pd
    def mock_kline_fn(symbol, start, end):
        if symbol == "300750.SZ":
            # 强趋势：60 天稳步上涨
            return pd.DataFrame({"date": [f"2025-01-{i+1:02d}" for i in range(60)],
                                 "close": [100 + i * 2 for i in range(60)]})
        else:
            # 弱趋势：60 天横盘
            return pd.DataFrame({"date": [f"2025-01-{i+1:02d}" for i in range(60)],
                                 "close": [100] * 60})

    result = confirm_buy_candidates(candidates, mock_kline_fn, config)

    assert len(result) == 1
    assert result[0]["symbol"] == "300750.SZ"
    assert result[0]["confirmed"] is True
```

- [ ] **Step 2: 运行测试确认失败**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_stock_scanner.py::test_confirm_buy_candidates_filters_holds -v
```

- [ ] **Step 3: 实现**

在 `stock_scanner.py` 末尾添加：

```python
def confirm_buy_candidates(
    candidates: list[dict],
    kline_fetcher,
    config,
    top_n: int = 10,
) -> list[dict]:
    """对扫描器的 BUY 候选用历史 K 线做二次确认。

    candidates: 扫描器输出的 BUY 列表
    kline_fetcher: callable(symbol, start_date, end_date) -> DataFrame
    config: StrategyConfig
    top_n: 最终返回数量

    返回: 确认后的列表，每项增加 confirmed/final_score/final_action 字段
    """
    from src.indicators.technical_indicators import compute_feature_row
    from src.strategy.signal_engine import build_signal

    confirmed = []
    for cand in candidates:
        symbol = cand["symbol"]
        try:
            df = kline_fetcher(symbol, "2024-01-01", "2025-12-31")
            if df.empty or len(df) < 60:
                cand["confirmed"] = False
                cand["final_score"] = 0.0
                cand["final_action"] = "HOLD"
                cand["confirm_reason"] = "历史数据不足"
                confirmed.append(cand)
                continue
            close_prices = df["close"].tolist()
            features = compute_feature_row(close_prices)
            signal = build_signal(symbol, features, config)
            cand["confirmed"] = signal["action"] == "BUY"
            cand["final_score"] = signal["technical_score"]
            cand["final_action"] = signal["action"]
            if not cand["confirmed"]:
                cand["confirm_reason"] = f"趋势评分{signal['technical_score']:.4f}，信号{signal['action']}"
            else:
                cand["confirm_reason"] = f"趋势评分{signal['technical_score']:.4f}，确认BUY"
        except Exception as e:
            cand["confirmed"] = False
            cand["final_score"] = 0.0
            cand["final_action"] = "HOLD"
            cand["confirm_reason"] = f"确认失败: {e}"
        confirmed.append(cand)

    # 排序：已确认的在前，按扫描器评分降序
    confirmed.sort(key=lambda x: (x["confirmed"], x["score"]), reverse=True)
    return confirmed[:top_n]
```

- [ ] **Step 4: 运行测试**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_stock_scanner.py -v
```

- [ ] **Step 5: 提交**

---

### Task 2: API 端点接入确认逻辑

**Files:**
- Modify: `src/api/routes_dashboard.py`

- [ ] **Step 1: 修改 scan 端点**

在 `scan_stock_pool` 函数中，扫描完成后调用确认逻辑：

```python
@router.post("/api/v1/dashboard/scan")
def scan_stock_pool(config: dict | None = None) -> dict:
    from src.data.providers.akshare_provider import _fetch_tencent_quotes_batch
    from src.strategy.stock_scanner import scan_market, confirm_buy_candidates
    from src.strategy.strategy_config import StrategyConfig

    cfg = config or {}
    top_n = int(cfg.get("top_n", 10))

    settings = Settings()
    strategy_config = StrategyConfig.from_settings(settings)
    provider = AkshareProvider()
    stock_list_df = provider.get_stock_list()
    stock_list = stock_list_df.to_dict("records")

    if not stock_list:
        return {"status": "no_catalog", "buy": [], "sell": [], "hold": [], "total_scanned": 0}

    # 第一轮：扫描器筛选
    result = scan_market(
        stock_list=stock_list,
        fetch_quotes_fn=lambda syms: _fetch_tencent_quotes_batch(syms),
        top_n=top_n * 3,  # 取更多候选给确认层
    )

    # 第二轮：用历史 K 线确认 BUY 候选
    def kline_fetcher(symbol, start, end):
        from datetime import datetime
        return provider.get_history(symbol, datetime.fromisoformat(start), datetime.fromisoformat(end))

    confirmed_buy = confirm_buy_candidates(
        result["buy"], kline_fetcher, strategy_config, top_n=top_n
    )

    result["buy"] = confirmed_buy
    return {"status": "ok", **result}
```

- [ ] **Step 2: 运行测试**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/ --ignore=tests/test_dashboard_api.py -q
```

- [ ] **Step 3: 提交**

---

### Task 3: 仪表盘展示确认状态

**Files:**
- Modify: `src/api/dashboard.html`

- [ ] **Step 1: 修改 `renderScanResult` 函数**

在表格中增加"确认状态"列：

```javascript
html += '<th>排名</th><th>股票</th><th>动作</th><th>评分</th><th>确认</th><th>核心原因</th>';
```

每行显示确认状态：

```javascript
const confirmCls = item.confirmed ? 'buy' : 'hold';
const confirmText = item.confirmed ? '已确认' : '未确认';
html += `<td><span class="scan-badge ${confirmCls}">${confirmText}</span></td>`;
```

- [ ] **Step 2: 验证**

- [ ] **Step 3: 提交**

---

## Acceptance Criteria

- 扫描器 BUY 候选经过历史 K 线确认后才显示
- 确认状态标记"已确认"/"未确认"
- 已确认的排在前面
- 现有测试不被破坏
- 扫描耗时 < 30 秒（K 线拉取是瓶颈）
