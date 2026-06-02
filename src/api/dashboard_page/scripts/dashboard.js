// 工作台相关 API 常量
const WORKBENCH_API = '/api/v1/dashboard/workbench';
const RUN_API = '/api/v1/dashboard/run';
const KILL_SWITCH_STATUS_API = '/api/v1/kill-switch/status';
const KILL_SWITCH_ACTIVATE_API = '/api/v1/kill-switch/activate';
const KILL_SWITCH_DEACTIVATE_API = '/api/v1/kill-switch/deactivate';
const PREFS_API = '/api/v1/dashboard/preferences';

function switchTab(btn, paneId) {
  btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.getElementById(paneId).classList.add('active');
}

function switchView(btn, viewId) {
  btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(viewId).classList.add('active');
  if (viewId === 'view-market') {
    refreshMarketQuotes();
  } else if (viewId === 'view-alpha') {
    loadAlphaAssets();
    loadAlphaTickets();
  }
}

function setExecMode(btn) {
  btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  execMode = btn.dataset.mode === 'decision' ? 'decision' : 'full';
  updateModeStatus();
  savePreferences();
}

function updateModeStatus() {
  const modeEl = document.getElementById('cfg-mode');
  const newPosEl = document.getElementById('cfg-new-pos');
  const statusEl = document.getElementById('mode-status');

  if (!modeEl || !newPosEl || !statusEl) return;

  const decisionMode = modeEl.value === 'real' ? 'Real (实盘决策)' : 'Mock (模拟)';
  const allowNewPos = newPosEl.classList.contains('on') ? '是' : '否';
  const execModeText = execMode === 'full' ? '完整链路' : '仅决策';

  statusEl.innerHTML = `
    <div>决策: <strong>${decisionMode}</strong> | 执行: <strong>${execModeText}</strong> | 新开仓: <strong>${allowNewPos}</strong></div>
    <div style="margin-top:4px">${execMode === 'decision' ? '⏸️ 只生成建议，不执行订单' : '▶️ 决策 → 目标仓位 → 执行 → 对账'}</div>
  `;
}

function setKillSwitchButton(active) {
  killSwitchActive = Boolean(active);
  const btn = document.querySelector('.kill-btn');
  btn.textContent = killSwitchActive ? '解除 KILL SWITCH' : 'KILL SWITCH';
}

function renderStatus(workbench, killStatus) {
  const modeRaw = normalizeText(workbench.mode, '--');
  document.getElementById('mode-pill').textContent = modeRaw === 'shadow' ? '影子模式' : modeRaw;
  document.getElementById('trade-date').textContent = formatDate(workbench.trade_date);
  document.getElementById('last-run').textContent = formatTime(workbench.last_run_at);

  const services = workbench.services || {};
  document.getElementById('db-dot').className = serviceDotClass(services.database);
  document.getElementById('llm-dot').className = serviceDotClass(services.llm);
  document.getElementById('mkt-dot').className = serviceDotClass(services.market);

  const active = killStatus.active ?? workbench.kill_switch?.active ?? false;
  setKillSwitchButton(active);
}

function showToast(message, type = 'info') {
  const existing = document.querySelector('.toast-notification');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = 'toast-notification';
  toast.style.cssText = `
    position: fixed;
    top: 60px;
    right: 20px;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    z-index: 10000;
    animation: slideIn 0.3s ease;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  `;

  if (type === 'success') {
    toast.style.background = 'var(--green)';
    toast.style.color = '#fff';
  } else if (type === 'error') {
    toast.style.background = 'var(--red)';
    toast.style.color = '#fff';
  } else {
    toast.style.background = 'var(--accent)';
    toast.style.color = '#fff';
  }

  toast.textContent = message;
  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 2000);
}

function savePreferences() {
  clearTimeout(_savePrefsTimer);
  const statusEl = document.getElementById('save-status');
  statusEl.textContent = '保存中...';
  statusEl.style.color = 'var(--yellow)';

  const prefs = {
    watchlist: document.getElementById('cfg-watchlist').value
      .split(',').map(s => s.trim()).filter(Boolean),
    capital_base: Number(document.getElementById('cfg-capital').value) * 10000,
    max_position_ratio: Number(document.getElementById('cfg-max-pos').value) / 100,
    stop_loss_ratio: Number(document.getElementById('cfg-stop-loss').value) / 100,
    max_daily_loss_ratio: Number(document.getElementById('cfg-max-daily').value) / 100,
    execution_mode: execMode,
  };

  fetch(PREFS_API, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(prefs),
  }).then(res => {
    if (res.ok) {
      statusEl.textContent = '已保存';
      statusEl.style.color = 'var(--green)';
      showToast('配置已保存', 'success');
      setTimeout(() => { statusEl.textContent = ''; }, 2000);
    } else {
      statusEl.textContent = '保存失败';
      statusEl.style.color = 'var(--red)';
      showToast('保存失败', 'error');
    }
  }).catch(() => {
    statusEl.textContent = '保存失败';
    statusEl.style.color = 'var(--red)';
    showToast('保存失败', 'error');
  });
}

function renderConfig(config) {
  if (!config || configHydrated) return;

  if (config.watchlist) {
    document.getElementById('cfg-watchlist').value = Array.isArray(config.watchlist)
      ? config.watchlist.join(',') : config.watchlist;
  }
  if (config.capital_base !== undefined) {
    const capitalWan = Number(config.capital_base) / 10000;
    document.getElementById('cfg-capital').value = capitalWan;
  }
  if (config.max_position_ratio !== undefined) {
    document.getElementById('cfg-max-pos').value = Number(config.max_position_ratio) * 100;
  }
  if (config.stop_loss_ratio !== undefined) {
    document.getElementById('cfg-stop-loss').value = Number(config.stop_loss_ratio) * 100;
  }
  if (config.max_daily_loss_ratio !== undefined) {
    document.getElementById('cfg-max-daily').value = Number(config.max_daily_loss_ratio) * 100;
  }
  if (config.allow_new_positions !== undefined) {
    document.getElementById('cfg-new-pos').classList.toggle('on', Boolean(config.allow_new_positions));
  }
  if (config.decision_mode) {
    document.getElementById('cfg-mode').value = config.decision_mode;
  }
  const mode = config.execution_mode === 'decision' ? 'decision' : 'full';
  const execButtons = document.querySelectorAll('#exec-mode button');
  execButtons.forEach(button => button.classList.toggle('active', button.dataset.mode === mode));
  execMode = mode;
  configHydrated = true;
}

function renderDecisions(list) {
  const rows = toList(list);
  const dataChanged = rows !== pag.decisions.data && JSON.stringify(rows) !== JSON.stringify(pag.decisions.data);
  pag.decisions.data = rows;
  if (dataChanged && rows.length >= PAGE_SIZE) pag.decisions.page = 0;
  const tb = document.getElementById('tb-decisions');
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="5" style="color:var(--dim)">暂无数据</td></tr>';
    document.getElementById('pag-decisions').innerHTML = '';
    return;
  }
  const page = pagSlice('decisions');
  tb.innerHTML = page.map(item => {
    const time = formatTime(pickFirst(item, ['created_at', 'timestamp']));
    const symbol = normalizeText(pickFirst(item, ['symbol', 'stock_code']));
    const action = normalizeText(pickFirst(item, ['action', 'parsed_action', 'signal'])).toUpperCase();
    const badge = action === 'BUY' ? 'badge-buy' : action === 'SELL' ? 'badge-sell' : 'badge-hold';
    const confidence = formatConfidence(item.confidence);
    const reasonRaw = pickFirst(item, ['reason', 'rationale', 'message'], '');
    const reason = normalizeText(reasonRaw, '--');
    return `<tr><td>${escapeHtml(time)}</td><td>${escapeHtml(symbol)}</td><td><span class="badge ${badge}">${escapeHtml(action)}</span></td><td>${escapeHtml(confidence)}</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(reason)}">${escapeHtml(reason)}</td></tr>`;
  }).join('');
  document.getElementById('pag-decisions').innerHTML = rows.length >= PAGE_SIZE ? renderPagControls('decisions') : '';
}

function renderOrders(list) {
  const rows = toList(list);
  const dataChanged = rows !== pag.orders.data && JSON.stringify(rows) !== JSON.stringify(pag.orders.data);
  pag.orders.data = rows;
  if (dataChanged && rows.length >= PAGE_SIZE) pag.orders.page = 0;
  const tb = document.getElementById('tb-orders');
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="6" style="color:var(--dim)">暂无数据</td></tr>';
    document.getElementById('pag-orders').innerHTML = '';
    return;
  }
  const page = pagSlice('orders');
  tb.innerHTML = page.map(item => {
    const time = formatTime(pickFirst(item, ['created_at', 'timestamp']));
    const symbol = normalizeText(pickFirst(item, ['symbol', 'stock_code']));
    const side = normalizeText(pickFirst(item, ['side', 'action', 'parsed_action'])).toUpperCase();
    const badge = side === 'BUY' ? 'badge-buy' : side === 'SELL' ? 'badge-sell' : 'badge-hold';
    const quantity = normalizeText(pickFirst(item, ['quantity', 'qty', 'target_quantity', 'target_value']));
    const price = formatCurrency(pickFirst(item, ['price', 'limit_price'], null));
    const status = normalizeText(item.status).toUpperCase();
    const statusBadge = status === 'FILLED' ? 'badge-filled' : status === 'PENDING' ? 'badge-pending' : status === 'ERROR' ? 'badge-error' : 'badge-hold';
    return `<tr><td>${escapeHtml(time)}</td><td>${escapeHtml(symbol)}</td><td><span class="badge ${badge}">${escapeHtml(side)}</span></td><td>${escapeHtml(quantity)}</td><td>${escapeHtml(price)}</td><td><span class="badge ${statusBadge}">${escapeHtml(status)}</span></td></tr>`;
  }).join('');
  document.getElementById('pag-orders').innerHTML = rows.length >= PAGE_SIZE ? renderPagControls('orders') : '';
}

function renderTargets(list) {
  const rows = toList(list);
  const dataChanged = rows !== pag.targets.data && JSON.stringify(rows) !== JSON.stringify(pag.targets.data);
  pag.targets.data = rows;
  if (dataChanged && rows.length >= PAGE_SIZE) pag.targets.page = 0;
  const tb = document.getElementById('tb-targets');
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="4" style="color:var(--dim)">暂无数据</td></tr>';
    document.getElementById('pag-targets').innerHTML = '';
    return;
  }
  const page = pagSlice('targets');
  tb.innerHTML = page.map(item => {
    const symbol = normalizeText(pickFirst(item, ['symbol', 'stock_code']));
    const quantity = normalizeText(pickFirst(item, ['target_quantity', 'quantity', 'target_value']));
    const weight = formatPercent(pickFirst(item, ['target_weight', 'target_position_ratio'], null));
    const reason = normalizeText(pickFirst(item, ['reason', 'rationale'], '--'));
    return `<tr><td>${escapeHtml(symbol)}</td><td>${escapeHtml(quantity)}</td><td>${escapeHtml(weight)}</td><td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(reason)}">${escapeHtml(reason)}</td></tr>`;
  }).join('');
  document.getElementById('pag-targets').innerHTML = rows.length >= PAGE_SIZE ? renderPagControls('targets') : '';
}

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

function renderErrorEvents(events) {
  const rows = toList(events);
  const dataChanged = rows !== pag.errors.data && JSON.stringify(rows) !== JSON.stringify(pag.errors.data);
  pag.errors.data = rows;
  if (dataChanged && rows.length >= PAGE_SIZE) pag.errors.page = 0;
  const tb = document.getElementById('tb-errors');
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="3" style="color:var(--dim)">暂无异常</td></tr>';
    document.getElementById('pag-errors').innerHTML = '';
    return;
  }
  const page = pagSlice('errors');
  tb.innerHTML = page.map(item => {
    const time = formatTime(pickFirst(item, ['created_at', 'timestamp', 'time']));
    const level = normalizeText(pickFirst(item, ['level', 'severity', 'event_type'])).toUpperCase();
    let messageRaw = pickFirst(item, ['message', 'summary', 'reason'], null);
    if (!messageRaw && item.payload) {
      if (typeof item.payload === 'object') {
        try {
          messageRaw = JSON.stringify(item.payload, null, 2);
        } catch (e) {
          messageRaw = String(item.payload);
        }
      } else {
        messageRaw = String(item.payload);
      }
    }
    const message = normalizeText(messageRaw, '--');
    return `<tr><td>${escapeHtml(time)}</td><td>${escapeHtml(level)}</td><td>${escapeHtml(message)}</td></tr>`;
  }).join('');
  document.getElementById('pag-errors').innerHTML = rows.length >= PAGE_SIZE ? renderPagControls('errors') : '';
}

function renderAlerts(alerts) {
  const rows = toList(alerts);
  const area = document.getElementById('alerts-area');
  if (!rows.length) {
    area.innerHTML = '<div class="alert-item info">系统就绪</div>';
    return;
  }
  area.innerHTML = rows.map(item => {
    const cls = toAlertLevel(item.level);
    const time = formatTime(pickFirst(item, ['created_at', 'timestamp', 'time']));
    const message = normalizeText(item.message, '--');
    return `<div class="alert-item ${cls}">[${escapeHtml(time)}] ${escapeHtml(message)}</div>`;
  }).join('');
}

function stageLabel(stage) {
  const tag = normalizeText(stage, 'stage').toLowerCase();
  if (tag === 'decision') return '决策';
  if (tag === 'target') return '目标仓位';
  if (tag === 'execute') return '执行';
  if (tag === 'reconcile') return '对账';
  if (tag === 'error') return '异常';
  if (tag === 'blocked') return '阻断';
  return tag;
}

function stageBodyHtml(step) {
  const stage = normalizeText(step.stage || step.name, '').toLowerCase();
  const items = toList(step.items);
  if (items.length) {
    const first = items[0] || {};
    if (first.target_position_ratio !== undefined || first.target_weight !== undefined) {
      const rows = items.map(item => {
        const symbol = escapeHtml(normalizeText(pickFirst(item, ['symbol', 'stock_code'])));
        const quantity = escapeHtml(normalizeText(pickFirst(item, ['target_quantity', 'quantity', 'target_value'])));
        const weight = escapeHtml(formatPercent(pickFirst(item, ['target_weight', 'target_position_ratio'], null)));
        return `<tr><td>${symbol}</td><td>${quantity}</td><td>${weight}</td></tr>`;
      }).join('');
      return `<table><tr><th>股票</th><th>目标数量</th><th>权重</th></tr>${rows}</table>`;
    }
    if (first.status !== undefined || first.limit_price !== undefined || first.quantity !== undefined) {
      const rows = items.map(item => {
        const symbol = escapeHtml(normalizeText(pickFirst(item, ['symbol', 'stock_code'])));
        const action = escapeHtml(normalizeText(pickFirst(item, ['action', 'parsed_action']), '--').toUpperCase());
        const qty = escapeHtml(normalizeText(pickFirst(item, ['quantity', 'qty']), '--'));
        const status = escapeHtml(normalizeText(item.status, '--').toUpperCase());
        return `<tr><td>${symbol}</td><td>${action}</td><td>${qty}</td><td>${status}</td></tr>`;
      }).join('');
      return `<table><tr><th>股票</th><th>方向</th><th>数量</th><th>状态</th></tr>${rows}</table>`;
    }
    const rows = items.map(item => {
      const symbol = escapeHtml(normalizeText(pickFirst(item, ['symbol', 'stock_code'])));
      const action = normalizeText(pickFirst(item, ['action', 'parsed_action', 'signal']), '--').toUpperCase();
      const confidence = escapeHtml(formatConfidence(item.confidence));
      const badgeClass = action === 'BUY' ? 'badge-buy' : action === 'SELL' ? 'badge-sell' : 'badge-hold';
      return `<tr><td>${symbol}</td><td><span class="badge ${badgeClass}">${escapeHtml(action)}</span></td><td>${confidence}</td></tr>`;
    }).join('');
    return `<table><tr><th>股票</th><th>动作</th><th>置信度</th></tr>${rows}</table>`;
  }
  const message = normalizeText(step.message || step.summary || step.detail, '--');
  if (stage === 'reconcile') {
    const match = message.match(/([+-]CNY [\d,]+(?:\.\d+)?)/);
    if (match) {
      const pnlLabel = match[1];
      const before = escapeHtml(message.slice(0, match.index));
      const after = escapeHtml(message.slice((match.index || 0) + pnlLabel.length));
      return `${before}<span style="color:var(--green)">${escapeHtml(pnlLabel)}</span>${after}`;
    }
  }
  return escapeHtml(message);
}

function renderTimeline(latestRun) {
  const timeline = document.getElementById('timeline');
  const steps = toList(latestRun?.steps);
  if (!steps.length) {
    timeline.innerHTML = '<div class="timeline-empty" id="timeline-empty">配置参数后点击「运行一轮模拟交易」开始</div>';
    return;
  }
  timeline.innerHTML = '';
  steps.forEach(step => {
    const stage = normalizeText(step.stage || step.name, 'stage').toLowerCase();
    const statusRaw = normalizeText(step.status, 'done').toLowerCase();
    const status = statusRaw === 'error' || statusRaw === 'failed' ? 'error' : statusRaw === 'running' || statusRaw === 'in_progress' ? 'running' : 'done';
    const time = formatTime(pickFirst(step, ['created_at', 'timestamp', 'time']));
    const div = document.createElement('div');
    div.className = `tl-step ${status}`;
    div.dataset.tag = stage;

    let stepCopy = {...step};
    if (stage === 'target' && execMode === 'decision') {
      stepCopy.message = '仅决策模式，目标仓位未计算';
    }

    div.innerHTML = `
      <div class="step-head">
        <span class="step-tag ${stage}">${escapeHtml(stageLabel(stage))}</span>
        <span class="step-time">${escapeHtml(time)}</span>
      </div>
      <div class="step-body">${stageBodyHtml(stepCopy)}</div>
    `;
    timeline.appendChild(div);
  });
  timeline.scrollTop = timeline.scrollHeight;
}

function addAlert(level, message) {
  const area = document.getElementById('alerts-area');
  const div = document.createElement('div');
  div.className = `alert-item ${toAlertLevel(level)}`;
  div.textContent = `[${new Date().toLocaleTimeString('zh-CN', { hour12: false })}] ${message}`;
  area.prepend(div);
  while (area.children.length > 10) area.lastChild.remove();
}

function renderWorkbench(data, killStatus) {
  renderStatus(data, killStatus || {});
  const config = { ...(data.config || {}), ...(data._serverPrefs || {}) };
  renderConfig(config);
  renderDecisions(data.history?.decisions || []);
  renderOrders(data.history?.orders || []);
  renderTargets(data.history?.targets || []);
  renderRisk(data.risk || {}, data.history?.targets || []);
  renderErrorEvents(data.history?.events || []);
  renderAlerts(data.risk?.alerts || []);
  renderTimeline(data.latest_run || { steps: [] });
}

async function loadDashboard() {
  try {
    const [workbenchRes, killStatusRes] = await Promise.all([
      fetch(WORKBENCH_API),
      fetch(KILL_SWITCH_STATUS_API),
    ]);
    const workbenchBody = await parseResponseBody(workbenchRes);
    const killStatusBody = await parseResponseBody(killStatusRes);

    if (!workbenchRes.ok) {
      throw new Error(extractErrorMessage(workbenchBody, `工作台加载失败 (${workbenchRes.status})`));
    }
    if (!killStatusRes.ok) {
      throw new Error(extractErrorMessage(killStatusBody, `Kill Switch 状态加载失败 (${killStatusRes.status})`));
    }

    let serverPrefs = null;
    try {
      const prefsRes = await fetch(PREFS_API);
      if (prefsRes.ok) {
        serverPrefs = await parseResponseBody(prefsRes);
      }
    } catch (_) {}

    if (serverPrefs && serverPrefs.watchlist) {
      workbenchBody._serverPrefs = serverPrefs;
    }

    renderWorkbench(workbenchBody, killStatusBody);
    await refreshMarketQuotes();
  } catch (error) {
    addAlert('err', `数据加载失败: ${error.message}`);
  }
}

function buildRunPayload() {
  const watchlist = document.getElementById('cfg-watchlist').value
    .split(',')
    .map(s => s.trim())
    .filter(Boolean);
  return {
    capital_base: Number(document.getElementById('cfg-capital').value) * 10000,
    watchlist,
    max_position_ratio: Number(document.getElementById('cfg-max-pos').value) / 100,
    stop_loss_ratio: Number(document.getElementById('cfg-stop-loss').value) / 100,
    max_daily_loss_ratio: Number(document.getElementById('cfg-max-daily').value) / 100,
    allow_new_positions: document.getElementById('cfg-new-pos').classList.contains('on'),
    decision_mode: document.getElementById('cfg-mode').value,
    execution_mode: execMode,
  };
}

function finishRun() {
  simRunning = false;
  const button = document.getElementById('run-btn');
  setButtonLoading(button, false, '运行一轮模拟交易');
}

const SCAN_API = '/api/v1/dashboard/scan';

async function triggerScan() {
  if (scanRunning) return;
  scanRunning = true;
  const btn = document.getElementById('scan-btn');
  setButtonLoading(btn, true, '扫描中...');
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
    const btn = document.getElementById('scan-btn');
    setButtonLoading(btn, false, '全市场扫描');
  }
}

function renderScanResult(data) {
  const area = document.getElementById('scan-content');
  if (data.status === 'no_catalog') {
    area.innerHTML = '<span style="color:var(--yellow)">股票列表不可用，请检查网络</span>';
    return;
  }

  let html = `<div class="scan-summary">已扫描 ${data.total_scanned} 只股票</div>`;

  const confirmedBuy = (data.buy || []).filter(item => item.confirmed);
  const unconfirmedBuy = (data.buy || []).filter(item => !item.confirmed);
  const holdItems = data.hold || [];
  const sellItems = data.sell || [];

  if (confirmedBuy.length > 0) {
    html += `<div class="scan-section-title">✅ 可执行买入信号 (${confirmedBuy.length})</div>`;
    html += '<div style="font-size:11px;color:var(--dim);margin-bottom:6px">扫描器评分高 + 趋势确认为 BUY，可考虑执行</div>';
    html += '<table class="scan-table"><thead><tr>';
    html += '<th>排名</th><th>股票</th><th>最终信号</th><th>评分</th><th>核心原因</th>';
    html += '</tr></thead><tbody>';
    confirmedBuy.forEach((item, idx) => {
      const scoreDisplay = item.final_score !== undefined
        ? `<div title="扫描器: ${item.score.toFixed(2)}\n趋势: ${item.final_score.toFixed(4)}"><span style="color:var(--muted);font-size:11px">${item.score.toFixed(2)}</span><span style="margin:0 4px">→</span><span style="font-weight:700">${item.final_score.toFixed(4)}</span></div>`
        : item.score.toFixed(4);
      html += `<tr>
        <td>${idx + 1}</td>
        <td>${escapeHtml(item.symbol)} ${escapeHtml(item.name || '')}</td>
        <td><span class="scan-badge buy">BUY ✓</span></td>
        <td style="font-weight:600">${scoreDisplay}</td>
        <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(item.confirm_reason || item.reason)}">${escapeHtml(item.confirm_reason || item.reason)}</td>
      </tr>`;
    });
    html += '</tbody></table>';
  }

  if (unconfirmedBuy.length > 0) {
    html += `<div class="scan-section-title" style="color:var(--yellow)">⚠️ 候选买入信号 (${unconfirmedBuy.length})</div>`;
    html += '<div style="font-size:11px;color:var(--dim);margin-bottom:6px">扫描器评分高但趋势未确认，仅供参考</div>';
    html += '<table class="scan-table"><thead><tr>';
    html += '<th>排名</th><th>股票</th><th>候选信号</th><th>评分</th><th>未确认原因</th>';
    html += '</tr></thead><tbody>';
    unconfirmedBuy.forEach((item, idx) => {
      const scoreDisplay = item.final_score !== undefined
        ? `<div title="扫描器: ${item.score.toFixed(2)}\n趋势: ${item.final_score.toFixed(4)}"><span style="color:var(--muted);font-size:11px">${item.score.toFixed(2)}</span><span style="margin:0 4px">→</span><span style="font-weight:700">${item.final_score.toFixed(4)}</span></div>`
        : item.score.toFixed(4);
      const reason = item.confirm_reason || item.reason;
      html += `<tr>
        <td>${idx + 1}</td>
        <td>${escapeHtml(item.symbol)} ${escapeHtml(item.name || '')}</td>
        <td><span class="scan-badge hold">BUY → ${escapeHtml(item.final_action || 'HOLD')}</span></td>
        <td style="font-weight:600">${scoreDisplay}</td>
        <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(reason)}">${escapeHtml(reason)}</td>
      </tr>`;
    });
    html += '</tbody></table>';
  }

  if (holdItems.length > 0 || sellItems.length > 0) {
    html += `<details style="margin-top:12px">`;
    html += `<summary style="cursor:pointer;color:var(--dim);font-size:12px">其他信号 (HOLD: ${holdItems.length}, SELL: ${sellItems.length})</summary>`;

    if (holdItems.length > 0) {
      html += `<div class="scan-section-title" style="margin-top:8px">持有信号 (${holdItems.length})</div>`;
      html += '<table class="scan-table"><thead><tr><th>股票</th><th>评分</th><th>原因</th></tr></thead><tbody>';
      holdItems.slice(0, 10).forEach(item => {
        html += `<tr><td>${escapeHtml(item.symbol)} ${escapeHtml(item.name || '')}</td><td>${item.score.toFixed(4)}</td><td>${escapeHtml(item.reason)}</td></tr>`;
      });
      html += '</tbody></table>';
    }

    if (sellItems.length > 0) {
      html += `<div class="scan-section-title" style="margin-top:8px">卖出信号 (${sellItems.length})</div>`;
      html += '<table class="scan-table"><thead><tr><th>股票</th><th>评分</th><th>原因</th></tr></thead><tbody>';
      sellItems.slice(0, 10).forEach(item => {
        html += `<tr><td>${escapeHtml(item.symbol)} ${escapeHtml(item.name || '')}</td><td>${item.score.toFixed(4)}</td><td>${escapeHtml(item.reason)}</td></tr>`;
      });
      html += '</tbody></table>';
    }

    html += `</details>`;
  }

  if (confirmedBuy.length === 0 && unconfirmedBuy.length === 0 && holdItems.length === 0 && sellItems.length === 0) {
    html += '<div style="color:var(--dim);text-align:center;padding:20px">未发现任何信号</div>';
  }

  area.innerHTML = html;
}

const BACKTEST_API = '/api/v1/dashboard/backtest';

async function triggerBacktest() {
  if (btRunning) return;
  const watchlist = document.getElementById('cfg-watchlist').value
    .split(',').map(s => s.trim()).filter(Boolean);
  if (!watchlist.length) { alert('请先填写观察列表'); return; }

  btRunning = true;
  const btn = document.getElementById('bt-btn');
  setButtonLoading(btn, true, '回测中...');
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
    const btn = document.getElementById('bt-btn');
    setButtonLoading(btn, false, '运行回测');
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

  let html = `<div class="bt-card">
    <div class="bt-row"><span class="bt-label">区间平均收益</span><span class="bt-value ${retCls}">${avgRet}%</span></div>
    <div class="bt-row"><span class="bt-label">最大回撤</span><span class="bt-value red">${worstDd}%</span></div>
    <div class="bt-row"><span class="bt-label">总交易次数</span><span class="bt-value">${s.total_trades}</span></div>
  </div>`;

  html += '<div class="factor-section"><h3>多因子选股分析</h3>';

  const factorNames = {
    momentum_20: '20日动量',
    momentum_60: '60日动量',
    ma20_gap: 'MA20偏离',
    ma60_gap: 'MA60偏离',
    volume_ratio_20: '量比',
    volatility_20: '波动率',
  };

  for (const r of data.results) {
    const fa = r.factor_analysis;
    if (!fa) continue;
    const actionCls = fa.action === 'BUY' ? 'buy' : fa.action === 'SELL' ? 'sell' : 'hold';
    const scoreColor = fa.technical_score >= fa.thresholds.buy ? 'green'
      : fa.technical_score <= fa.thresholds.sell ? 'red' : 'var(--fg)';

    html += `<div class="factor-card">
      <div class="fc-header">
        <span class="fc-symbol">${escapeHtml(r.symbol)}</span>
        <span class="fc-action ${actionCls}">${fa.action}</span>
      </div>
      <div class="fc-score">综合评分: <span style="color:${scoreColor};font-weight:700">${fa.technical_score.toFixed(4)}</span>
        (买入≥${fa.thresholds.buy} / 卖出≤${fa.thresholds.sell})</div>`;

    const contributions = fa.contributions || {};
    const weights = fa.weights || {};
    const features = fa.features || {};
    const maxAbs = Math.max(0.001, ...Object.values(contributions).map(v => Math.abs(v)));

    for (const [key, label] of Object.entries(factorNames)) {
      const contrib = contributions[key] || 0;
      const val = features[key] !== undefined ? features[key] : 0;
      const weight = weights[key] || 0;
      const pct = Math.min(Math.abs(contrib) / maxAbs * 100, 100);
      const barCls = contrib >= 0 ? 'positive' : 'negative';
      const sign = contrib >= 0 ? '+' : '';

      html += `<div class="factor-bar-row">
        <span class="factor-bar-label">${label}</span>
        <div class="factor-bar-track">
          <div class="factor-bar-fill ${barCls}" style="width:${pct}%"></div>
        </div>
        <span class="factor-bar-value">${sign}${(contrib * 100).toFixed(2)}%</span>
      </div>`;
    }

    html += '</div>';
  }
  html += `<div style="margin-top:8px;font-size:11px;color:var(--dim);border-top:1px solid var(--border);padding-top:6px">
    策略: 确定性量化基线 (momentum + MA偏离 + 量比 + 波动率)
    <br>信号: BUY≥0.55 & RSI∈[45,72] | SELL≤0.20 | RSI≥80 | MA20偏离≤-5%
  </div>`;
  html += '</div>';

  area.innerHTML = html;
}

async function triggerRun() {
  if (simRunning) return;
  simRunning = true;
  const button = document.getElementById('run-btn');
  setButtonLoading(button, true, '运行中...');
  renderTimeline({
    steps: [{
      stage: 'decision',
      status: 'running',
      timestamp: new Date().toISOString(),
      message: '请求已提交，等待后端返回结果...',
    }],
  });

  try {
    const res = await fetch(RUN_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildRunPayload()),
    });
    const body = await parseResponseBody(res);
    if (!res.ok) {
      throw new Error(extractErrorMessage(body, `运行失败 (${res.status})`));
    }
    renderWorkbench(body, { active: killSwitchActive });
    addAlert('info', '本轮运行完成');
  } catch (error) {
    addAlert('err', `运行失败: ${error.message}`);
    await loadDashboard();
  } finally {
    finishRun();
  }
}

async function killSwitch() {
  const willActivate = !killSwitchActive;
  const confirmText = willActivate
    ? '确认触发 Kill Switch？将停止所有交易动作。'
    : '确认解除 Kill Switch？';
  if (!confirm(confirmText)) return;

  const endpoint = willActivate ? KILL_SWITCH_ACTIVATE_API : KILL_SWITCH_DEACTIVATE_API;
  try {
    const res = await fetch(endpoint, { method: 'POST' });
    const body = await parseResponseBody(res);
    if (!res.ok) {
      throw new Error(extractErrorMessage(body, `Kill Switch 操作失败 (${res.status})`));
    }
    addAlert(willActivate ? 'err' : 'info', willActivate ? 'Kill Switch 已激活' : 'Kill Switch 已解除');
    await loadDashboard();
  } catch (error) {
    addAlert('err', `Kill Switch 操作失败: ${error.message}`);
  }
}

function setButtonLoading(btn, loading, originalText) {
  if (loading) {
    btn.disabled = true;
    btn.dataset.originalText = btn.textContent;
    btn.innerHTML = '<span class="loading-spinner"></span>' + originalText;
  } else {
    btn.disabled = false;
    btn.textContent = btn.dataset.originalText || originalText;
  }
}
