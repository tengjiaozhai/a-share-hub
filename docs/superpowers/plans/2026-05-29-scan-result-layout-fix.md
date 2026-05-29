# 扫描结果布局优化 实施计划

**Goal:** 修复扫描结果的布局问题——评分说明、持有/卖出条数、表格可读性。

**Architecture:** 修改后端 scan 端点限制每组返回数量，前端增加评分列 tooltip 和标签。

**Tech Stack:** Python, HTML/CSS/JS

---

## File Structure

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/api/routes_dashboard.py` | 修改 | scan 端点限制每组 top_n 条 |
| `src/api/dashboard.html` | 修改 | 评分列 tooltip + 列头标签 |

---

### Task 1: 限制持有/卖出每组返回 10 条

**Files:**
- Modify: `src/api/routes_dashboard.py`

- [ ] **Step 1: 修改 scan 端点**

```python
    # scan_market 取 3x 给 BUY 确认用，HOLD/SELL 只取 top_n
    result = scan_market(
        stock_list=stock_list,
        fetch_quotes_fn=lambda syms: _fetch_tencent_quotes_batch(syms),
        top_n=top_n * 3,
    )

    # 第二轮：用历史 K 线确认 BUY 候选
    def kline_fetcher(symbol, start, end):
        return provider.get_history(symbol, datetime.fromisoformat(start), datetime.fromisoformat(end))

    confirmed_buy = confirm_buy_candidates(
        result["buy"], kline_fetcher, strategy_config, top_n=top_n
    )
    result["buy"] = confirmed_buy
    # HOLD/SELL 截断到 top_n
    result["hold"] = result["hold"][:top_n]
    result["sell"] = result["sell"][:top_n]
```

- [ ] **Step 2: Commit**

---

### Task 2: 评分列增加 tooltip 说明

**Files:**
- Modify: `src/api/dashboard.html`

- [ ] **Step 1: 修改评分列显示**

评分列改为双行显示，带 tooltip：
```javascript
const scoreDisplay = sec.hasConfirm && item.final_score !== undefined
  ? `<div title="扫描器评分: ${item.score.toFixed(2)} (实时因子)\n趋势评分: ${item.final_score.toFixed(4)} (60日因子)" style="cursor:help">` +
    `<span style="color:var(--muted);font-size:11px">扫描${item.score.toFixed(2)}</span>` +
    `<span style="margin:0 4px">→</span>` +
    `<span style="font-weight:700">${item.final_score.toFixed(4)}</span>` +
    `</div>`
  : item.score.toFixed(4);
```

- [ ] **Step 2: 修改评分列头**

```javascript
if (sec.hasConfirm) html += '<th title="扫描器评分→趋势评分">评分</th>';
else html += '<th>评分</th>';
```

- [ ] **Step 3: Commit**

---

## Acceptance Criteria

- 持有/卖出每组最多显示 10 条
- 评分列显示 `扫描0.95 → 0.0470` 格式，hover 有 tooltip 解释
- 不破坏现有功能
