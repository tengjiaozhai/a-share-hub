// src/api/static/js/views/dashboard.js

function initDashboard() {
  // Bind events for dashboard view
}

function renderDashboard() {
  loadWorkbench();
}

async function loadWorkbench() {
  try {
    const [workbench, killStatus] = await Promise.all([
      DashboardAPI.getWorkbench(),
      DashboardAPI.getKillSwitch(),
    ]);
    renderWorkbench(workbench, killStatus);
  } catch (err) {
    showToast('加载工作台失败: ' + err.message, 'error');
  }
}

function renderWorkbench(data, killStatus) {
  renderStatus(data, killStatus);
  renderConfig(data.config);
  renderDecisions(data.decisions || []);
  renderOrders(data.orders || []);
  renderTargets(data.targets || []);
  renderRisk(data.risk, data.targets);
  renderErrorEvents(data.errors || []);
  renderAlerts(data.alerts || []);
  renderTimeline(data.latest_run);
}

function renderStatus(workbench, killStatus) {
  const statusEl = document.getElementById('service-status');
  if (!statusEl) return;
  const services = workbench.services || {};
  statusEl.innerHTML = Object.entries(services).map(([name, status]) => `
    <span class="service-dot ${serviceDotClass(status)}"></span>
    <span>${escapeHtml(name)}</span>
  `).join('');
  setKillSwitchButton(killStatus.active);
}

function setKillSwitchButton(active) {
  State.killSwitch = active;
  const btn = document.getElementById('kill-switch-btn');
  if (!btn) return;
  btn.textContent = active ? '解除风控' : '触发风控';
  btn.className = active ? 'btn-danger active' : 'btn-danger';
}

function renderConfig(config) {
  if (!config || State.configHydrated) return;
  State.configHydrated = true;
  const modeEl = document.getElementById('cfg-mode');
  if (modeEl) modeEl.value = config.mode || 'mock';
  updateModeStatus();
}

function renderDecisions(list) {
  State.pagination.decisions.data = list;
  const root = document.getElementById('decisions-pane');
  if (!root) return;
  const items = pagSlice('decisions');
  root.innerHTML = items.length ? `
    <table>
      <thead><tr><th>时间</th><th>标的</th><th>决策</th><th>置信度</th></tr></thead>
      <tbody>${items.map(d => `
        <tr>
          <td>${formatTime(d.created_at)}</td>
          <td>${escapeHtml(d.symbol)}</td>
          <td>${escapeHtml(d.action)}</td>
          <td>${formatConfidence(d.confidence)}</td>
        </tr>
      `).join('')}</tbody>
    </table>
    ${renderPagControls('decisions')}
  ` : '<span style="color:var(--dim)">暂无决策记录</span>';
}

function renderOrders(list) {
  State.pagination.orders.data = list;
  const root = document.getElementById('orders-pane');
  if (!root) return;
  const items = pagSlice('orders');
  root.innerHTML = items.length ? `
    <table>
      <thead><tr><th>时间</th><th>标的</th><th>方向</th><th>数量</th><th>状态</th></tr></thead>
      <tbody>${items.map(o => `
        <tr>
          <td>${formatTime(o.created_at)}</td>
          <td>${escapeHtml(o.symbol)}</td>
          <td>${escapeHtml(o.side)}</td>
          <td>${formatNumber(o.quantity)}</td>
          <td>${escapeHtml(o.status)}</td>
        </tr>
      `).join('')}</tbody>
    </table>
    ${renderPagControls('orders')}
  ` : '<span style="color:var(--dim)">暂无订单记录</span>';
}

function renderTargets(list) {
  State.pagination.targets.data = list;
  const root = document.getElementById('targets-pane');
  if (!root) return;
  const items = pagSlice('targets');
  root.innerHTML = items.length ? `
    <table>
      <thead><tr><th>标的</th><th>目标持仓</th><th>当前持仓</th><th>漂移</th></tr></thead>
      <tbody>${items.map(t => `
        <tr>
          <td>${escapeHtml(t.symbol)}</td>
          <td>${formatNumber(t.target_quantity)}</td>
          <td>${formatNumber(t.current_quantity)}</td>
          <td>${formatSignedPercent(t.drift)}</td>
        </tr>
      `).join('')}</tbody>
    </table>
    ${renderPagControls('targets')}
  ` : '<span style="color:var(--dim)">暂无目标仓位</span>';
}

function renderRisk(risk, targets) {
  const root = document.getElementById('risk-summary');
  if (!root || !risk) return;
  root.innerHTML = `
    <div class="bt-card">
      <div class="bt-row"><span class="bt-label">总市值</span><span class="bt-value">${formatCurrency(risk.total_value)}</span></div>
      <div class="bt-row"><span class="bt-label">持仓数</span><span class="bt-value">${targets ? targets.length : 0}</span></div>
      <div class="bt-row"><span class="bt-label">现金</span><span class="bt-value">${formatCurrency(risk.cash)}</span></div>
    </div>
  `;
}

function renderErrorEvents(events) {
  State.pagination.errors.data = events;
  const root = document.getElementById('errors-pane');
  if (!root) return;
  const items = pagSlice('errors');
  root.innerHTML = items.length ? `
    <table>
      <thead><tr><th>时间</th><th>级别</th><th>消息</th></tr></thead>
      <tbody>${items.map(e => `
        <tr>
          <td>${formatTime(e.created_at)}</td>
          <td><span class="badge badge-${toAlertLevel(e.level)}">${escapeHtml(e.level)}</span></td>
          <td>${escapeHtml(e.message)}</td>
        </tr>
      `).join('')}</tbody>
    </table>
    ${renderPagControls('errors')}
  ` : '<span style="color:var(--dim)">暂无错误事件</span>';
}

function renderAlerts(alerts) {
  const root = document.getElementById('alerts-pane');
  if (!root) return;
  if (!alerts || alerts.length === 0) {
    root.innerHTML = '<span style="color:var(--dim)">暂无告警</span>';
    return;
  }
  root.innerHTML = alerts.map(a => `
    <div class="alert-item alert-${toAlertLevel(a.level)}">
      <span class="alert-time">${formatTime(a.created_at)}</span>
      <span class="alert-msg">${escapeHtml(a.message)}</span>
    </div>
  `).join('');
}

function renderTimeline(latestRun) {
  const root = document.getElementById('timeline-pane');
  if (!root || !latestRun) return;
  const steps = latestRun.steps || [];
  root.innerHTML = `
    <div class="timeline">
      ${steps.map(step => `
        <div class="timeline-step ${step.status === 'completed' ? 'completed' : ''}">
          <div class="timeline-dot"></div>
          <div class="timeline-content">
            <strong>${escapeHtml(step.name)}</strong>
            <span>${formatTime(step.completed_at)}</span>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function stageLabel(stage) {
  const labels = {
    'input': '输入构建',
    'decision': '决策生成',
    'target': '目标规划',
    'execution': '订单执行',
    'reconciliation': '对账检查',
  };
  return labels[stage] || stage;
}

function stageBodyHtml(step) {
  if (!step.details) return '';
  return `<pre>${escapeHtml(JSON.stringify(step.details, null, 2))}</pre>`;
}