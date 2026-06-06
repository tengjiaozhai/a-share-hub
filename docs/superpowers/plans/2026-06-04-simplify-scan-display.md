# 简化扫描结果显示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化扫描结果的显示方式，将"BUY → HOLD"改为更清晰的两列展示

**Architecture:** 修改前端JavaScript显示逻辑，分离扫描器结论和确认后结论

**Tech Stack:** JavaScript, HTML

---

## File Structure

- Modify: `src/api/dashboard_page/scripts/dashboard.js:560-582`

---

### Task 1: 修改候选买入信号的显示格式

**Files:**
- Modify: `src/api/dashboard_page/scripts/dashboard.js:565-576`

- [ ] **Step 1: 修改表头和显示逻辑**

将 `dashboard.js:565-576` 的代码修改为：

```javascript
html += '<table class="scan-table"><thead><tr>';
html += '<th>排名</th><th>股票</th><th>扫描器</th><th>确认结果</th><th>评分</th><th>未确认原因</th>';
html += '</tr></thead><tbody>';
unconfirmedBuy.forEach((item, idx) => {
  const scoreDisplay = item.final_score !== undefined
    ? `<div title="扫描器: ${item.score.toFixed(2)}\n趋势: ${item.final_score.toFixed(4)}"><span style="color:var(--muted);font-size:11px">${item.score.toFixed(2)}</span><span style="margin:0 4px">→</span><span style="font-weight:700">${item.final_score.toFixed(4)}</span></div>`
    : item.score.toFixed(4);
  const reason = item.confirm_reason || item.reason;
  html += `<tr>
    <td>${idx + 1}</td>
    <td>${escapeHtml(item.symbol)} ${escapeHtml(item.name || '')}</td>
    <td><span class="scan-badge buy">BUY</span></td>
    <td><span class="scan-badge hold">${escapeHtml(item.final_action || 'HOLD')}</span></td>
    <td style="font-weight:600">${scoreDisplay}</td>
    <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(reason)}">${escapeHtml(reason)}</td>
  </tr>`;
});
```

- [ ] **Step 2: 测试显示效果**

启动服务并访问 dashboard 页面，点击扫描按钮查看候选买入信号的显示是否正确。

- [ ] **Step 3: 提交修改**

```bash
git add src/api/dashboard_page/scripts/dashboard.js
git commit -m "fix: simplify scan result display - separate scanner and confirmation columns"
```
