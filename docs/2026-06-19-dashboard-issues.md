# Dashboard UX Issues - 2026-06-19

**审查日期:** 2026-06-19  
**审查页面:** http://13.214.201.113:8000/dashboard  
**审查人:** 产品经理  
**状态:** 待处理

---

## 问题汇总

| 优先级 | 数量 | 描述 |
|--------|------|------|
| 高 | 2 | 影响核心功能或用户体验 |
| 中 | 3 | 影响产品细节和可用性 |
| 低 | 2 | 优化建议，提升体验 |

---

## 高优先级 Issues

### Issue #1: 90天和YTD窗口数据与30天相同，缺少提示

**严重程度:** 高  
**类型:** 数据展示 / 用户预期  
**发现位置:** 区间表现对比面板

**问题描述:**
用户切换到 90天 或 YTD 窗口时，显示的日期范围和样本数与 30天 完全相同：
- 30天: 2026-05-08 ~ 2026-06-06, 30 个交易日样本
- 90天: 2026-05-08 ~ 2026-06-06, 30 个交易日样本
- YTD: 2026-05-08 ~ 2026-06-06, 30 个交易日样本

**复现步骤:**
1. 打开 Dashboard 页面
2. 点击"30天"按钮，记录显示的日期范围和样本数
3. 点击"90天"按钮，对比显示内容
4. 点击"YTD"按钮，对比显示内容

**影响:**
- 用户可能误以为数据有误或系统故障
- 用户无法知道数据不足，可能做出错误判断
- 降低产品可信度

**建议方案:**

**方案 A: 显示数据不足提示（推荐）**
```javascript
// 在 renderPerformance 函数中
if (windowReturn !== undefined && sampleCount) {
  const windowDays = { '7d': 7, '30d': 30, '90d': 90, 'ytd': 365 };
  const expectedDays = windowDays[selectedPerformanceWindow];
  const insufficientData = sampleCount < expectedDays * 0.8; // 80% 阈值
  
  let warningHtml = '';
  if (insufficientData) {
    warningHtml = `
      <div class="range-card-warning" style="color: var(--yellow); font-size: 11px; margin-top: 4px;">
        ⚠️ 数据不足 ${expectedDays} 天，仅显示最近 ${sampleCount} 天
      </div>
    `;
  }
  
  rangeDataEl.innerHTML = `
    <div class="range-card">
      <div class="range-card-head">
        <span class="range-card-label">${escapeHtml(normalizeWindowLabel(selectedPerformanceWindow))}收益</span>
        <span class="range-card-window">${escapeHtml(startText)} ~ ${escapeHtml(endText)}</span>
      </div>
      <div class="range-card-value ${returnClass}">${escapeHtml(returnText)}</div>
      <div class="range-card-sub">${escapeHtml(String(sampleCount))} 个交易日样本</div>
      ${warningHtml}
    </div>
  `;
}
```

**方案 B: 禁用不可用的窗口按钮**
如果数据不足，将 90天 和 YTD 按钮设为 disabled 状态，并添加 tooltip 提示"数据不足"。

**验收标准:**
- [ ] 当数据不足时，显示明确的提示文字
- [ ] 提示文字颜色使用黄色警告色
- [ ] 不影响数据充足时的正常显示

---

### Issue #2: 运行记录卡片缺少明确的"可查看详情"提示

**严重程度:** 高  
**类型:** 交互设计 / 可发现性  
**发现位置:** 运行中心

**问题描述:**
运行记录卡片显示"完整案件"或"概要"，但没有明确的视觉提示告诉用户点击卡片可以查看案件视图（决策、订单、对账等详细信息）。

**当前状态:**
```
手动 已完成 wrk-20260618-090424-00cf5d
2026-06-18 a 完整案件
决策 1 目标 1 订单 1 观察 1 CNY -92.32
```

**影响:**
- 用户可能不知道可以点击卡片查看详细决策、订单等信息
- 案件视图的核心功能（决策、订单、对账）使用率可能很低
- 降低产品的深度使用价值

**建议方案:**

**方案 A: 添加"点击查看案件"提示（推荐）**
在卡片底部添加提示文字：
```html
<div class="run-card-hint">
  <span class="hint-icon">👆</span>
  <span class="hint-text">点击查看案件详情</span>
</div>
```

CSS 样式：
```css
.run-card-hint {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--stroke);
  font-size: 11px;
  color: var(--muted);
  opacity: 0.7;
  transition: opacity 0.2s;
}

.run-card:hover .run-card-hint {
  opacity: 1;
  color: var(--accent);
}
```

**方案 B: 添加视觉指示器**
在卡片右上角添加小图标（如 `>` 或 `📋`），表示可以点击查看。

**方案 C: 首次访问引导**
对于首次访问的用户，显示一个 toast 提示："点击运行记录可查看完整案件详情"

**验收标准:**
- [ ] 卡片明确提示用户可以点击查看详情
- [ ] 提示不影响现有卡片的紧凑布局
- [ ] hover 状态下提示更加明显

---

## 中优先级 Issues

### Issue #3: Footer 文案不够清晰

**严重程度:** 中  
**类型:** 文案 / 信息传达  
**发现位置:** 运行中心底部

**问题描述:**
Footer 显示"已加载 16 条最近记录"，没有明确说明是否还有更多记录。

**当前状态:**
```
已加载 16 条最近记录
```

**影响:**
- 用户不知道是否已经看到全部记录
- 可能误以为还有更多记录需要加载
- 文案不够明确，增加认知负担

**建议方案:**

**方案 A: 明确显示总数（推荐）**
```javascript
// 在 renderRunCenter 函数中
if (footer) {
  footer.innerHTML = historyPanelHasMore
    ? `<button type="button" class="run-load-more" onclick="loadMoreHistoryRuns()" ${historyPanelLoading ? 'disabled' : ''}>
        ${historyPanelLoading ? '加载中...' : `加载更多 (已显示 ${historyRuns.length} 条)`}
       </button>`
    : `<div class="run-center-status">已显示全部 ${historyRuns.length} 条记录</div>`;
}
```

**方案 B: 显示进度指示**
如果知道总记录数，显示"已显示 16 / 100 条"

**验收标准:**
- [ ] 文案明确说明是否已显示全部记录
- [ ] 如果有更多记录，显示"加载更多"按钮
- [ ] 如果已显示全部，显示"已显示全部 X 条记录"

---

### Issue #4: 案件阶段按钮的激活状态不够明显

**严重程度:** 中  
**类型:** 视觉设计 / 反馈  
**发现位置:** 案件视图阶段按钮

**问题描述:**
点击"决策""订单"等按钮后，激活状态的视觉反馈不够强烈，用户可能不清楚当前查看的是哪个阶段。

**当前状态:**
按钮激活时只有轻微的背景色变化，不够醒目。

**影响:**
- 用户可能不清楚当前查看的是哪个阶段
- 降低操作的确定感和满意度
- 可能导致误操作

**建议方案:**

**增强激活状态样式（推荐）**
```css
.case-stage-rail button.active {
  background: var(--accent);
  color: var(--bg);
  border-color: var(--accent);
  box-shadow: 0 2px 8px rgba(77, 212, 198, 0.3);
  transform: translateY(-2px);
}

.case-stage-rail button.active strong {
  color: var(--bg);
  font-weight: 800;
}
```

**验收标准:**
- [ ] 激活按钮与非激活按钮有明显的视觉差异
- [ ] 激活按钮有阴影或提升效果
- [ ] 激活按钮的数字计数更加醒目

---

### Issue #5: 决策表格时间显示"--"不友好

**严重程度:** 中  
**类型:** 数据展示 / 用户体验  
**发现位置:** 案件视图 - 决策 Tab

**问题描述:**
决策表格的时间列显示"--"，用户无法知道决策的具体时间。

**当前状态:**
```
--    600519.SH    BUY    85%    贵州茅台作为白酒行业龙头...
```

**影响:**
- 用户无法知道决策的具体时间
- "--" 可能让用户误以为数据缺失或系统错误
- 降低信息的完整性

**建议方案:**

**方案 A: 显示实际时间（推荐）**
如果后端返回了时间数据，显示实际时间：
```javascript
const time = formatTime(pickFirst(item, ['created_at', 'timestamp']));
// 如果 time 为 '--'，尝试从父级数据获取
if (time === '--' && parentRun?.created_at) {
  time = formatTime(parentRun.created_at);
}
```

**方案 B: 改为更友好的文案**
如果确实没有时间数据，改为"未知"或"未记录"：
```javascript
const time = formatTime(pickFirst(item, ['created_at', 'timestamp']));
const displayTime = time === '--' ? '未记录' : time;
```

**验收标准:**
- [ ] 时间列显示实际时间或友好的提示文字
- [ ] 不显示 "--" 这种模糊的占位符
- [ ] 保持表格布局不变

---

## 低优先级 Issues

### Issue #6: 区间切换缺少加载状态

**严重程度:** 低  
**类型:** 交互反馈 / 性能感知  
**发现位置:** 区间表现对比面板

**问题描述:**
切换 7天/30天/90天/YTD 时，没有加载动画，用户可能以为页面卡住。

**影响:**
- 如果 API 调用较慢，用户可能以为页面卡住
- 缺少操作反馈，降低交互的流畅感
- 用户可能重复点击按钮

**建议方案:**

**添加加载动画（推荐）**
```javascript
async function loadPerformancePanel(market, window) {
  const win = window || selectedPerformanceWindow || '7d';
  selectedPerformanceWindow = win;
  
  // 显示加载状态
  const canvas = document.getElementById('perf-nav-canvas');
  const rangeData = document.getElementById('range-data');
  if (canvas) {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = 'rgba(120, 120, 120, 0.5)';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('加载中...', canvas.width / 2, canvas.height / 2);
  }
  if (rangeData) {
    rangeData.innerHTML = '<span class="range-placeholder">加载中...</span>';
  }
  
  try {
    const res = await fetch(`${PERFORMANCE_API}?market=${market}&account_kind=auto&window=${win}`);
    if (!res.ok) return;
    const data = await parseResponseBody(res);
    renderPerformance(data);
  } catch (_) {}
}
```

**验收标准:**
- [ ] 切换区间时显示加载状态
- [ ] 加载完成后正常显示数据
- [ ] 不影响现有的数据更新逻辑

---

### Issue #7: 运行卡片盈亏显示不够直观

**严重程度:** 低  
**类型:** 视觉设计 / 信息传达  
**发现位置:** 运行中心

**问题描述:**
运行卡片显示"CNY -92.32"，负号不够明显，用户需要仔细看才能知道是亏损。

**当前状态:**
```
CNY -92.32
```

**影响:**
- 用户需要仔细看才能知道是亏损
- 盈亏信息不够醒目，降低决策效率
- 不符合交易系统的视觉惯例

**建议方案:**

**增强盈亏视觉表现（推荐）**
```css
.run-mini-chip.pnl {
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
}

.run-mini-chip.pnl.green {
  background: rgba(34, 197, 94, 0.15);
  color: var(--green);
  border: 1px solid rgba(34, 197, 94, 0.3);
}

.run-mini-chip.pnl.red {
  background: rgba(239, 68, 68, 0.15);
  color: var(--danger);
  border: 1px solid rgba(239, 68, 68, 0.3);
}
```

JavaScript:
```javascript
const pnl = formatSignedCurrency(run.net_pnl);
const pnlClass = run.net_pnl > 0 ? 'green' : run.net_pnl < 0 ? 'red' : '';
return `<span class="run-mini-chip pnl ${pnlClass}">${escapeHtml(pnl)}</span>`;
```

**验收标准:**
- [ ] 盈利使用绿色背景和边框
- [ ] 亏损使用红色背景和边框
- [ ] 数字更加醒目（加粗）
- [ ] 不影响现有布局

---

## 下一步行动

### 建议修复顺序

1. **Issue #1** - 数据不足提示（高优先级，影响用户信任）
2. **Issue #2** - 卡片可点击提示（高优先级，提升功能发现性）
3. **Issue #3** - Footer 文案优化（中优先级，改善信息传达）
4. **Issue #5** - 时间显示优化（中优先级，提升信息完整性）
5. **Issue #4** - 按钮激活状态（中优先级，增强交互反馈）
6. **Issue #7** - 盈亏视觉增强（低优先级，提升视觉表现）
7. **Issue #6** - 加载状态（低优先级，优化性能感知）

### 预估工作量

| Issue | 预估时间 | 难度 |
|-------|---------|------|
| #1 | 30 分钟 | 低 |
| #2 | 20 分钟 | 低 |
| #3 | 10 分钟 | 低 |
| #4 | 15 分钟 | 低 |
| #5 | 20 分钟 | 中 |
| #6 | 15 分钟 | 低 |
| #7 | 15 分钟 | 低 |
| **总计** | **约 2 小时** | - |

---

## 附录

### 已验证的功能

以下功能在审查中验证为正常工作：

- ✅ 曲线标题动态更新（7天/30天/90天/YTD）
- ✅ 区间数据显示窗口元数据（收益、日期范围、样本数）
- ✅ 运行记录筛选（全部/手动/自动）
- ✅ 案件视图 Tab 切换（概览/决策/目标仓位/订单/对账/异常）
- ✅ Cursor 分页机制
- ✅ 案件阶段计数准确
- ✅ 所有 30 个测试通过

### 测试环境

- 浏览器: Chrome (headless)
- 页面: http://13.214.201.113:8000/dashboard
- 数据: 16 条运行记录（6 手动 / 10 自动）

---

**文档创建时间:** 2026-06-19  
**最后更新:** 2026-06-19
