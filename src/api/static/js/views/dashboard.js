// src/api/static/js/views/dashboard.js

const WORKBENCH_API = '/api/v1/dashboard/workbench';
const KILL_SWITCH_STATUS_API = '/api/v1/kill-switch/status';
const PREFS_API = '/api/v1/dashboard/preferences';

let execMode = 'full';
let killSwitchActive = false;

function initDashboard() {
  var addStockInput = document.getElementById('cfg-add-stock');
  if (addStockInput) {
    addStockInput.addEventListener('keypress', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        var stockCode = addStockInput.value.trim();
        if (stockCode) {
          var watchlistEl = document.getElementById('cfg-watchlist');
          if (watchlistEl) {
            var current = watchlistEl.value;
            watchlistEl.value = current ? current + ',' + stockCode : stockCode;
            addStockInput.value = '';
          }
        }
      }
    });
  }

  updateModeStatus();
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
  if (!config || State.configHydrated) return;
  State.configHydrated = true;
  const modeEl = document.getElementById('cfg-mode');
  if (modeEl) modeEl.value = config.mode || 'mock';
  updateModeStatus();
}

function renderDecisions(list) {
  State.pagination.decisions.data = list;
  const root = document.getElementById('tb-decisions');
  if (!root) return;
  const items = pagSlice('decisions');
  if (!items.length) {
    root.innerHTML = '<tr><td colspan="5" style="color:var(--dim)">暂无决策记录</td></tr>';
    return;
  }
  root.innerHTML = items.map(d => `
    <tr>
      <td>${formatTime(d.created_at)}</td>
      <td>${escapeHtml(d.symbol)}</td>
      <td>${escapeHtml(d.action)}</td>
      <td>${formatConfidence(d.confidence)}</td>
      <td>${escapeHtml(normalizeText(pickFirst(d, ['reason', 'summary', 'rationale']), '--'))}</td>
    </tr>
  `).join('');
  const tab = root.closest('.tab-pane');
  if (tab) {
    let ctrl = tab.querySelector('.pagination');
    if (!ctrl) {
      ctrl = document.createElement('div');
      tab.appendChild(ctrl);
    }
    ctrl.outerHTML = renderPagControls('decisions');
  }
}

function renderOrders(list) {
  State.pagination.orders.data = list;
  const root = document.getElementById('tb-orders');
  if (!root) return;
  const items = pagSlice('orders');
  if (!items.length) {
    root.innerHTML = '<tr><td colspan="6" style="color:var(--dim)">暂无订单记录</td></tr>';
    return;
  }
  root.innerHTML = items.map(o => `
    <tr>
      <td>${formatTime(o.created_at)}</td>
      <td>${escapeHtml(o.symbol)}</td>
      <td>${escapeHtml(o.side)}</td>
      <td>${formatNumber(o.quantity)}</td>
      <td>${formatNumber(pickFirst(o, ['price', 'limit_price'], '--'))}</td>
      <td>${escapeHtml(o.status)}</td>
    </tr>
  `).join('');
  const tab = root.closest('.tab-pane');
  if (tab) {
    let ctrl = tab.querySelector('.pagination');
    if (!ctrl) {
      ctrl = document.createElement('div');
      tab.appendChild(ctrl);
    }
    ctrl.outerHTML = renderPagControls('orders');
  }
}

function renderTargets(list) {
  State.pagination.targets.data = list;
  const root = document.getElementById('tb-targets');
  if (!root) return;
  const items = pagSlice('targets');
  if (!items.length) {
    root.innerHTML = '<tr><td colspan="4" style="color:var(--dim)">暂无目标仓位</td></tr>';
    return;
  }
  root.innerHTML = items.map(t => `
    <tr>
      <td>${escapeHtml(t.symbol)}</td>
      <td>${formatNumber(t.target_quantity)}</td>
      <td>${formatNumber(t.current_quantity)}</td>
      <td>${formatSignedPercent(t.drift)}</td>
    </tr>
  `).join('');
  const tab = root.closest('.tab-pane');
  if (tab) {
    let ctrl = tab.querySelector('.pagination');
    if (!ctrl) {
      ctrl = document.createElement('div');
      tab.appendChild(ctrl);
    }
    ctrl.outerHTML = renderPagControls('targets');
  }
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
  State.pagination.errors.data = events;
  const root = document.getElementById('tb-errors');
  if (!root) return;
  const items = pagSlice('errors');
  if (!items.length) {
    root.innerHTML = '<tr><td colspan="3" style="color:var(--dim)">暂无错误事件</td></tr>';
    return;
  }
  root.innerHTML = items.map(e => `
    <tr>
      <td>${formatTime(e.created_at)}</td>
      <td><span class="badge badge-${toAlertLevel(e.level)}">${escapeHtml(e.level)}</span></td>
      <td>${escapeHtml(e.message)}</td>
    </tr>
  `).join('');
  const tab = root.closest('.tab-pane');
  if (tab) {
    let ctrl = tab.querySelector('.pagination');
    if (!ctrl) {
      ctrl = document.createElement('div');
      tab.appendChild(ctrl);
    }
    ctrl.outerHTML = renderPagControls('errors');
  }
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
// 同步配置到表单（外部可调用）
function populateConfigForm(config) {
  if (!config) return;
  var capitalEl = document.getElementById('cfg-capital');
  if (capitalEl) capitalEl.value = config.capital || 100;

  var watchlistEl = document.getElementById('cfg-watchlist');
  if (watchlistEl) watchlistEl.value = (config.watchlist || []).join(',');

  var maxPosEl = document.getElementById('cfg-max-pos');
  if (maxPosEl) maxPosEl.value = config.maxPosition || 20;

  var stopLossEl = document.getElementById('cfg-stop-loss');
  if (stopLossEl) stopLossEl.value = config.stopLoss || -5;

  var maxDailyEl = document.getElementById('cfg-max-daily');
  if (maxDailyEl) maxDailyEl.value = config.maxDailyLoss || -3;

  var newPosEl = document.getElementById('cfg-new-pos');
  if (newPosEl) {
    if (config.allowNewPosition) {
      newPosEl.classList.add('on');
    } else {
      newPosEl.classList.remove('on');
    }
  }
}

// Tab 切换
function switchTab(btn, tabId) {
  document.querySelectorAll('.tab-bar button').forEach(function(b) { b.classList.remove('active'); });
  document.querySelectorAll('.tab-pane').forEach(function(p) { p.classList.remove('active'); });
  btn.classList.add('active');
  var tabPane = document.getElementById(tabId);
  if (tabPane) tabPane.classList.add('active');
}

// 执行模式切换
function setExecMode(btn) {
  document.querySelectorAll('#exec-mode button').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  execMode = btn.dataset.mode || 'full';
  State.execMode = execMode;
  updateModeStatus();
}

// 更新模式状态显示
function updateModeStatus() {
  var modeStatus = document.getElementById('mode-status');
  if (!modeStatus) return;

  var configMode = document.getElementById('cfg-mode');
  var mode = configMode ? configMode.value : 'mock';
  var allowNewEl = document.getElementById('cfg-new-pos');
  var allowNew = allowNewEl ? allowNewEl.classList.contains('on') : true;
  var decisionLabel = mode === 'real' ? 'Real (实盘决策)' : 'Mock (模拟)';
  var execLabel = execMode === 'full' ? '完整链路' : '仅决策';
  var hint = execMode === 'decision'
    ? '⏸️ 只生成建议，不执行订单'
    : '▶️ 决策 → 目标仓位 → 执行 → 对账';

  modeStatus.innerHTML =
    '决策: <strong>' + decisionLabel + '</strong> | ' +
    '执行: <strong>' + execLabel + '</strong> | ' +
    '新开仓: <strong>' + (allowNew ? '是' : '否') + '</strong><br>' +
    hint;
}

// 保存配置
async function savePreferences() {
  syncConfigFromForm();
  var config = getConfig();

  try {
    await saveConfig(config);
    var saveStatus = document.getElementById('save-status');
    if (saveStatus) {
      saveStatus.textContent = '配置已保存';
      saveStatus.style.color = 'var(--green)';
      setTimeout(function() { saveStatus.textContent = ''; }, 3000);
    }
  } catch (error) {
    addAlert('err', '保存配置失败: ' + error.message);
  }
}

// 运行模拟
async function triggerRun() {
  var runBtn = document.getElementById('run-btn');
  if (runBtn) {
    runBtn.disabled = true;
    runBtn.textContent = '运行中...';
  }

  try {
    await runSimulation();
    addAlert('info', '模拟运行已启动');
    setTimeout(loadDashboard, 2000);
  } catch (error) {
    addAlert('err', '运行失败: ' + error.message);
  } finally {
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.textContent = '运行一轮模拟交易';
    }
  }
}

// 运行回测
async function triggerBacktest() {
  var startEl = document.getElementById('cfg-bt-start');
  var endEl = document.getElementById('cfg-bt-end');
  var startDate = startEl ? startEl.value : '';
  var endDate = endEl ? endEl.value : '';

  if (!startDate || !endDate) {
    addAlert('warn', '请选择回测日期范围');
    return;
  }

  var btBtn = document.getElementById('bt-btn');
  if (btBtn) {
    btBtn.disabled = true;
    btBtn.textContent = '回测中...';
  }

  try {
    var result = await runBacktest(startDate, endDate);
    var btResult = document.getElementById('bt-result');
    if (btResult) {
      btResult.textContent = '回测完成: ' + (result.message || '成功');
    }
  } catch (error) {
    addAlert('err', '回测失败: ' + error.message);
  } finally {
    if (btBtn) {
      btBtn.disabled = false;
      btBtn.textContent = '运行回测';
    }
  }
}

// 运行扫描
async function triggerScan() {
  var scanBtn = document.getElementById('scan-btn');
  var scanContent = document.getElementById('scan-content');

  if (scanBtn) {
    scanBtn.disabled = true;
    scanBtn.textContent = '扫描中...';
  }

  if (scanContent) {
    scanContent.textContent = '正在扫描全市场...';
  }

  try {
    var result = await runScan();
    if (scanContent) {
      scanContent.textContent = '扫描完成: ' + ((result && result.stocks && result.stocks.length) || 0) + ' 只股票';
    }
  } catch (error) {
    if (scanContent) {
      scanContent.textContent = '扫描失败: ' + error.message;
    }
  } finally {
    if (scanBtn) {
      scanBtn.disabled = false;
      scanBtn.textContent = '全市场扫描';
    }
  }
}

// 快捷键处理
document.addEventListener('keydown', function(e) {
  if (e.ctrlKey && e.key === 'Enter') {
    e.preventDefault();
    triggerRun();
  }
  if (e.ctrlKey && e.key === 's') {
    e.preventDefault();
    savePreferences();
  }
});

// 工具函数：截断文本
function truncateText(text, maxLen) {
  if (!text) return '--';
  if (text.length <= maxLen) return text;
  return text.substring(0, maxLen) + '...';
}
