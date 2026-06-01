// src/api/static/js/views/dashboard.js

function initDashboard() {
  // Bind events for dashboard view
}

function renderDashboard() {
  loadDashboard();
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

    // 加载服务端偏好
    let serverPrefs = null;
    try {
      const prefsRes = await fetch(PREFS_API);
      if (prefsRes.ok) {
        serverPrefs = await parseResponseBody(prefsRes);
      }
    } catch (_) {}

    // 合并服务端偏好到 config
    if (serverPrefs && serverPrefs.watchlist) {
      workbenchBody._serverPrefs = serverPrefs;
    }

    renderWorkbench(workbenchBody, killStatusBody);
    await refreshMarketQuotes();
  } catch (error) {
    addAlert('err', `数据加载失败: ${error.message}`);
  }
}

function renderWorkbench(data, killStatus) {
  renderStatus(data, killStatus || {});
  // 合并服务端偏好到 config（服务端偏好优先于 API config）
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

function setKillSwitchButton(active) {
  killSwitchActive = Boolean(active);
  const btn = document.querySelector('.kill-btn');
  if (!btn) return;
  btn.textContent = killSwitchActive ? '解除 KILL SWITCH' : 'KILL SWITCH';
}

function renderConfig(config) {
  if (!config || configHydrated) return;
  configHydrated = true;
  const modeEl = document.getElementById('cfg-mode');
  if (modeEl) modeEl.value = config.mode || 'mock';
  updateModeStatus();
}

function renderDecisions(list) {
  pag.decisions.data = list;
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
  pag.orders.data = list;
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
  pag.targets.data = list;
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
  pag.errors.data = events;
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
  const rows = toList(alerts);
  const area = document.getElementById('alerts-area');
  if (!area) return;
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

function renderTimeline(latestRun) {
  const timeline = document.getElementById('timeline');
  if (!timeline) return;
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

function addAlert(level, message) {
  const area = document.getElementById('alerts-area');
  if (!area) return;
  const div = document.createElement('div');
  div.className = `alert-item ${toAlertLevel(level)}`;
  div.textContent = `[${new Date().toLocaleTimeString('zh-CN', { hour12: false })}] ${message}`;
  area.prepend(div);
  while (area.children.length > 10) area.lastChild.remove();
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

async function parseResponseBody(res) {
  const text = await res.text();
  if (!text) return '';
  try {
    return JSON.parse(text);
  } catch (_) {
    return text;
  }
}

async function refreshMarketQuotes() {
  const symbols = buildQuoteSymbols();
  if (!symbols.length) {
    renderMarketQuotes([]);
    return;
  }
  try {
    const res = await fetch('/api/v1/market/bulk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(symbols),
    });
    if (!res.ok) {
      renderMarketQuotes([]);
      return;
    }
    const data = await res.json();
    renderMarketQuotes(Array.isArray(data) ? data : []);
  } catch (error) {
    renderMarketQuotes([]);
  }
}

function buildQuoteSymbols() {
  return document.getElementById('cfg-watchlist').value
    .split(',')
    .map(s => s.trim().toUpperCase())
    .filter(Boolean)
    .slice(0, 10);
}

function renderMarketQuotes(quotes) {
  const tb = document.getElementById('tb-market-full');
  if (!tb) return;
  const rows = toList(quotes);
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="12" class="market-empty">暂无行情数据</td></tr>';
    return;
  }
  const now = new Date().toLocaleTimeString('zh-CN', {hour12:false});
  tb.innerHTML = rows.map(item => {
    const symbol = normalizeText(item.symbol, '--');
    const name = normalizeText(item.name, '');
    const price = formatNumber(item.price);
    const change = formatNumber(item.change);
    const changePercent = formatNumber(item.change_percent);
    const open = formatNumber(item.open);
    const high = formatNumber(item.high);
    const low = formatNumber(item.low);
    const volume = formatVolume(item.volume);
    const turnover = formatNumber(item.turnover);
    const amplitude = formatNumber(item.amplitude);
    const volumeRatio = formatNumber(item.volume_ratio);
    
    const changeClass = item.change > 0 ? 'positive' : item.change < 0 ? 'negative' : '';
    
    return `<tr>
      <td>${now}</td>
      <td><strong>${escapeHtml(symbol)}</strong><br><small>${escapeHtml(name)}</small></td>
      <td class="${changeClass}">${price}</td>
      <td class="${changeClass}">${change}</td>
      <td class="${changeClass}">${changePercent}%</td>
      <td>${open}</td>
      <td>${high}</td>
      <td>${low}</td>
      <td>${volume}</td>
      <td>${turnover}%</td>
      <td>${amplitude}%</td>
      <td>${volumeRatio}</td>
    </tr>`;
  }).join('');
}