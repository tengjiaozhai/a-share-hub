# 仪表盘体验优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复仪表盘 8 个体验问题，提升工作台的可用性和信息密度。

**Architecture:** 所有改动集中在 `src/api/dashboard.html` 一个文件，不改后端 API。CSS 样式调整 + JS 逻辑优化 + HTML 文案改进。

**Tech Stack:** HTML/CSS/JavaScript（单文件仪表盘）

---

## File Structure

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/api/dashboard.html` | 修改 | CSS + HTML + JS 全部改动 |

---

### Task 1: 风控面板空状态提示

**Files:**
- Modify: `src/api/dashboard.html` (renderRisk 函数 + CSS)

- [ ] **Step 1: 添加空状态 CSS**

在 `.risk-card` 样式后添加：

```css
.risk-empty{font-size:12px;color:var(--dim);font-style:italic}
```

- [ ] **Step 2: 修改 renderRisk 函数**

```javascript
function renderRisk(risk, targets) {
  const targetList = toList(targets);
  const targetCount = risk.active_target_count ?? targetList.length;
  document.getElementById('risk-targets').textContent = targetCount;
  document.getElementById('risk-open-orders').textContent = risk.open_orders ?? 0;

  const concentrationRaw = risk.concentration_ratio ?? Math.max(0, ...targetList.map(t => Number(pickFirst(t, ['target_weight', 'target_position_ratio'], 0)) || 0));
  const concentration = Number(concentrationRaw) || 0;
  const concentrationEl = document.getElementById('risk-concentration');
  concentrationEl.textContent = concentration > 0 ? `${(concentration * 100).toFixed(1)}%` : '无持仓';
  concentrationEl.className = `risk-value ${concentration > 0.3 ? 'red' : concentration > 0.2 ? 'yellow' : 'green'}`;

  const pnl = Number(pickFirst(risk, ['daily_pnl', 'pnl', 'today_pnl'], 0)) || 0;
  const pnlEl = document.getElementById('risk-pnl');
  pnlEl.textContent = pnl !== 0 ? formatCurrency(pnl) : '今日无交易';
  pnlEl.className = `risk-value ${pnl > 0 ? 'green' : pnl < 0 ? 'red' : ''}`;
}
```

- [ ] **Step 3: 验证**

- [ ] **Step 4: Commit**

---

### Task 2: 回测日期默认值改为"最近3个月"

**Files:**
- Modify: `src/api/dashboard.html` (HTML input defaults + JS init)

- [ ] **Step 1: 修改 HTML 默认值**

将 `cfg-bt-start` 和 `cfg-bt-end` 的 value 改为动态计算：

```html
<input type="date" id="cfg-bt-start">
<input type="date" id="cfg-bt-end">
```

- [ ] **Step 2: 在 loadDashboard 之前添加初始化**

```javascript
(function initBacktestDates() {
  const end = new Date();
  const start = new Date();
  start.setMonth(start.getMonth() - 3);
  const fmt = d => d.toISOString().split('T')[0];
  document.getElementById('cfg-bt-start').value = fmt(start);
  document.getElementById('cfg-bt-end').value = fmt(end);
})();
```

- [ ] **Step 3: 验证**

- [ ] **Step 4: Commit**

---

### Task 3: 行情 Tab 添加更新时间列

**Files:**
- Modify: `src/api/dashboard.html` (market table header + renderMarketQuotes)

- [ ] **Step 1: 修改表头**

```html
<th>更新时间</th><th>股票</th><th>最新价</th>...
```

- [ ] **Step 2: 修改 renderMarketQuotes**

在 `<tr>` 中添加时间列，使用 `new Date().toLocaleTimeString('zh-CN', {hour12:false})`。

- [ ] **Step 3: 验证**

- [ ] **Step 4: Commit**

---

### Task 4: 保存按钮视觉优化

**Files:**
- Modify: `src/api/dashboard.html` (CSS + HTML)

- [ ] **Step 1: 修改 save-btn 样式**

```css
.save-btn{
  background:var(--green);border:none;color:#fff;
  padding:8px 16px;border-radius:8px;font-size:12px;font-weight:600;
  cursor:pointer;transition:.15s;width:100%;margin-top:4px;
}
.save-btn:hover{background:#16a34a}
.save-btn:active{transform:scale(.97)}
```

- [ ] **Step 2: 调整布局**

将保存按钮和状态文字放在独立一行，与运行按钮分开。

- [ ] **Step 3: 验证**

- [ ] **Step 4: Commit**

---

### Task 5: 手动添加股票 placeholder 优化

**Files:**
- Modify: `src/api/dashboard.html` (placeholder 文案)

- [ ] **Step 1: 修改 placeholder**

```html
<input type="text" id="cfg-add-stock" placeholder="输入代码后按回车添加，如 600519.SH">
```

- [ ] **Step 2: 验证**

- [ ] **Step 3: Commit**

---

### Task 6: 止损阈值添加单位显示

**Files:**
- Modify: `src/api/dashboard.html` (label 文案)

- [ ] **Step 1: 修改 label**

```html
<label>止损阈值 (%)</label>
```

确认已有 `%` 单位。如果已有则跳过。

- [ ] **Step 2: Commit**

---

### Task 7: 回测结果增加策略解释

**Files:**
- Modify: `src/api/dashboard.html` (renderBacktestResult)

- [ ] **Step 1: 在回测结果卡片底部添加策略说明**

```javascript
html += `<div style="margin-top:8px;font-size:11px;color:var(--dim)">
  策略: 确定性量化基线 (momentum + MA偏离 + 量比 + 波动率)
  <br>信号: BUY≥0.55 & RSI∈[45,72] | SELL≤0.20 | RSI≥80 | MA20偏离≤-5%
</div>`;
```

- [ ] **Step 2: 验证**

- [ ] **Step 3: Commit**

---

### Task 8: 告警区域增强

**Files:**
- Modify: `src/api/dashboard.html` (renderAlerts)

- [ ] **Step 1: 修改 renderAlerts 默认文案**

```javascript
function renderAlerts(alerts) {
  const rows = toList(alerts);
  const area = document.getElementById('alerts-area');
  if (!rows.length) {
    area.innerHTML = '<div class="alert-item info">系统就绪</div>';
    return;
  }
  // ... existing logic
}
```

- [ ] **Step 2: 验证**

- [ ] **Step 3: Commit**

---

## Acceptance Criteria

- 风控面板无交易时显示"今日无交易"/"无持仓"，而非 ¥0.00/0.0%
- 回测日期默认"最近3个月"，无需手动修改
- 行情 Tab 有"更新时间"列
- 保存按钮绿色醒目，与运行按钮视觉区分
- 手动添加股票 placeholder 有示例提示
- 回测结果底部有策略公式说明
- 告警区域简洁明了
