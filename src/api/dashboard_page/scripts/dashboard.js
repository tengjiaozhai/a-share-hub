// 工作台相关 API 常量
const WORKBENCH_API = '/api/v1/dashboard/workbench';
const KILL_SWITCH_STATUS_API = '/api/v1/kill-switch/status';
const KILL_SWITCH_ACTIVATE_API = '/api/v1/kill-switch/activate';
const KILL_SWITCH_DEACTIVATE_API = '/api/v1/kill-switch/deactivate';
const PREFS_API = '/api/v1/dashboard/preferences';
const PERFORMANCE_API = '/api/v1/dashboard/performance';
const AUTOMATION_API = '/api/v1/dashboard/automation';
const HISTORY_API = '/api/v1/dashboard/history';

function displayTimeValue(raw) {
  var formatted = formatTime(raw);
  return formatted === '--' ? '未记录' : formatted;
}

function animateKPIValue(element, newValue, formatFn, duration) {
  if (!element || !formatFn) return;
  duration = duration || 600;
  var startText = element.textContent;
  var startMatch = startText.match(/([+-]?\d*\.?\d+)/);
  var newMatch = String(newValue).match(/([+-]?\d*\.?\d+)/);
  if (!startMatch || !newMatch) {
    element.textContent = formatFn(newValue);
    return;
  }
  var startVal = parseFloat(startMatch[1]);
  var endVal = parseFloat(newMatch[1]);
  if (startVal === endVal || !isFinite(startVal) || !isFinite(endVal)) {
    element.textContent = formatFn(newValue);
    return;
  }
  var prefix = startText.substring(0, startMatch.index);
  var startTime = performance.now();
  function update(currentTime) {
    var elapsed = currentTime - startTime;
    var progress = Math.min(elapsed / duration, 1);
    var eased = 1 - Math.pow(1 - progress, 4);
    var current = startVal + (endVal - startVal) * eased;
    element.textContent = prefix + formatFn(current);
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}

function addRippleToButton(button) {
  button.addEventListener('click', function(e) {
    var rect = button.getBoundingClientRect();
    var x = e.clientX - rect.left;
    var y = e.clientY - rect.top;
    var ripple = document.createElement('span');
    ripple.style.cssText = 'position:absolute;border-radius:50%;background:rgba(255,255,255,0.25);pointer-events:none;transform:scale(0);animation:rippleExpand 0.5s ease-out forwards;';
    var size = Math.max(rect.width, rect.height) * 2;
    ripple.style.width = size + 'px';
    ripple.style.height = size + 'px';
    ripple.style.left = (x - size / 2) + 'px';
    ripple.style.top = (y - size / 2) + 'px';
    button.style.position = 'relative';
    button.style.overflow = 'hidden';
    button.appendChild(ripple);
    setTimeout(function() { ripple.remove(); }, 600);
  });
}

function showCaseDrawerSkeleton() {
  var shell = document.getElementById('case-shell');
  if (!shell) return;
  var existing = shell.querySelector('.case-skeleton-overlay');
  if (existing) return;
  var overlay = document.createElement('div');
  overlay.className = 'case-skeleton-overlay';
  overlay.innerHTML = '<div class="case-skeleton">' +
    '<div class="case-skeleton-bar" style="width: 40%"></div>' +
    '<div class="case-skeleton-bar" style="width: 70%"></div>' +
    '<div class="case-skeleton-bar" style="width: 60%"></div>' +
    '<div class="case-skeleton-bar" style="width: 80%"></div>' +
    '<div class="case-skeleton-bar" style="width: 30%"></div>' +
    '</div>';
  shell.style.position = 'relative';
  shell.appendChild(overlay);
}

function hideCaseDrawerSkeleton() {
  var overlay = document.querySelector('.case-skeleton-overlay');
  if (overlay) overlay.remove();
}

function isCaseDrawerOpen() {
  return document.getElementById('case-drawer')?.classList.contains('open');
}

function openCaseDrawer(runId) {
  var drawer = document.getElementById('case-drawer');
  var backdrop = document.getElementById('drawer-backdrop');
  if (!drawer || !backdrop) return;
  if (drawer.dataset.activeRun === runId && drawer.classList.contains('open')) {
    return;
  }
  drawer.dataset.activeRun = runId;
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');
  backdrop.classList.add('open');
  backdrop.setAttribute('aria-hidden', 'false');
  showCaseDrawerSkeleton();
}

function closeCaseDrawer() {
  var drawer = document.getElementById('case-drawer');
  var backdrop = document.getElementById('drawer-backdrop');
  if (!drawer || !backdrop) return;
  drawer.classList.remove('open');
  drawer.setAttribute('aria-hidden', 'true');
  backdrop.classList.remove('open');
  backdrop.setAttribute('aria-hidden', 'true');
}

function switchTab(btn, paneId) {
  const isCasePane = normalizeText(paneId, '').startsWith('case-pane-');
  const buttonGroup = btn?.parentElement;
  if (buttonGroup) {
    buttonGroup.querySelectorAll('button').forEach(b => b.classList.remove('active'));
  }
  if (btn) btn.classList.add('active');

  if (isCasePane) {
    const caseShell = btn?.closest('.case-shell') || document;
    caseShell.querySelectorAll('.case-stage-pane').forEach(pane => pane.classList.remove('active'));
  } else {
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
  }

  const pane = document.getElementById(paneId);
  if (pane) pane.classList.add('active');
  selectedCaseStage = paneId;
}

function setPerformanceWindow(window, btn) {
  selectedPerformanceWindow = window || '7d';
  const pills = document.querySelectorAll('#perf-range-pills .pill-btn');
  pills.forEach(pill => {
    pill.classList.toggle('active', pill.dataset.window === selectedPerformanceWindow);
  });
  if (btn) btn.classList.add('active');
  const market = document.getElementById('cfg-market')?.value || 'a';
  loadPerformancePanel(market, selectedPerformanceWindow);
}

function switchView(btn, viewId) {
  btn.parentElement.querySelectorAll('button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(viewId).classList.add('active');
  if (viewId === 'view-market') {
    marketInit();
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

  const innerTradeDate = document.getElementById('inner-trade-date');
  const innerLastRun = document.getElementById('inner-last-run');
  if (innerTradeDate) innerTradeDate.textContent = formatDate(workbench.trade_date);
  if (innerLastRun) innerLastRun.textContent = formatTime(workbench.last_run_at);

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
    market: document.getElementById('cfg-market').value,
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

  if (config.watchlist && config.watchlist.length > 0) {
    document.getElementById('cfg-watchlist').value = Array.isArray(config.watchlist)
      ? config.watchlist.join(',') : config.watchlist;
  }
  if (config.market) {
    document.getElementById('cfg-market').value = config.market;
  }
  // 根据市场过滤观察列表
  filterWatchlistByMarket();
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
    const time = displayTimeValue(pickFirst(item, ['created_at', 'timestamp']));
    const symbol = normalizeText(pickFirst(item, ['symbol', 'stock_code']));
    const action = normalizeText(pickFirst(item, ['action', 'parsed_action', 'signal'])).toUpperCase();
    const badge = action === 'BUY' ? 'badge-buy' : action === 'SELL' ? 'badge-sell' : 'badge-hold';
    const confidence = formatConfidence(item.confidence);
    const reasonRaw = pickFirst(item, ['reason', 'rationale', 'message'], '');
    const reason = normalizeText(reasonRaw, '--');
    return `<tr>
      <td>${escapeHtml(time)}</td>
      <td><div class="cell-stack"><span class="cell-primary">${escapeHtml(symbol)}</span><span class="cell-secondary">${escapeHtml(normalizeText(item.model_name, '模型输出'))}</span></div></td>
      <td><span class="badge ${badge}">${escapeHtml(action)}</span></td>
      <td>${escapeHtml(confidence)}</td>
      <td><div class="cell-stack"><span class="cell-primary">${escapeHtml(reason)}</span><span class="cell-secondary wrap">${escapeHtml(normalizeText(item.prompt_hash, ''))}</span></div></td>
    </tr>`;
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
    tb.innerHTML = '<tr><td colspan="8" style="color:var(--dim)">暂无数据</td></tr>';
    document.getElementById('pag-orders').innerHTML = '';
    return;
  }
  const page = pagSlice('orders');
  tb.innerHTML = page.map(item => {
    const time = displayTimeValue(pickFirst(item, ['created_at', 'timestamp']));
    const symbol = normalizeText(pickFirst(item, ['symbol', 'stock_code']));
    const side = normalizeText(pickFirst(item, ['side', 'action', 'parsed_action'])).toUpperCase();
    const badge = side === 'BUY' ? 'badge-buy' : side === 'SELL' ? 'badge-sell' : 'badge-hold';
    const quantity = normalizeText(pickFirst(item, ['quantity', 'qty', 'target_quantity', 'target_value']));
    const price = formatCurrency(pickFirst(item, ['fill_price', 'price', 'limit_price'], null));
    const fee = formatCurrency(pickFirst(item, ['fee'], 0));
    const pnl = Number(pickFirst(item, ['pnl_delta', 'pnl'], 0)) || 0;
    const pnlClass = pnl > 0 ? 'green' : pnl < 0 ? 'red' : '';
    const pnlText = pnl !== 0 ? formatCurrency(pnl) : '-';
    const status = normalizeText(item.status).toUpperCase();
    const statusBadge = status === 'FILLED' ? 'badge-filled' : status === 'PENDING' ? 'badge-pending' : status === 'ERROR' ? 'badge-error' : 'badge-hold';
    return `<tr>
      <td>${escapeHtml(time)}</td>
      <td><div class="cell-stack"><span class="cell-primary">${escapeHtml(symbol)}</span><span class="cell-secondary">${escapeHtml(normalizeText(item.execution_order_id, '执行单'))}</span></div></td>
      <td><span class="badge ${badge}">${escapeHtml(side)}</span></td>
      <td>${escapeHtml(quantity)}</td>
      <td>${escapeHtml(price)}</td>
      <td>${escapeHtml(fee)}</td>
      <td class="${pnlClass}">${escapeHtml(pnlText)}</td>
      <td><span class="badge ${statusBadge}">${escapeHtml(status)}</span></td>
    </tr>`;
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
    return `<tr>
      <td><div class="cell-stack"><span class="cell-primary">${escapeHtml(symbol)}</span><span class="cell-secondary">${escapeHtml(normalizeText(item.target_position_id, '目标输出'))}</span></div></td>
      <td>${escapeHtml(quantity)}</td>
      <td>${escapeHtml(weight)}</td>
      <td><div class="cell-stack"><span class="cell-primary">${escapeHtml(reason)}</span><span class="cell-secondary wrap">${escapeHtml(normalizeText(item.expires_at, ''))}</span></div></td>
    </tr>`;
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

function formatPercent(value) {
  const num = Number(value) || 0;
  const sign = num > 0 ? '+' : '';
  return `${sign}${(num * 100).toFixed(2)}%`;
}

function renderPerformance(performance) {
  const perf = performance || {};
  const todayEl = document.getElementById('perf-today');
  const monthEl = document.getElementById('perf-month');
  const drawdownEl = document.getElementById('perf-drawdown');
  const rangeDataEl = document.getElementById('range-data');
  const curveTitleEl = document.getElementById('nav-curve-title');
  document.querySelectorAll('#perf-range-pills .pill-btn').forEach(button => {
    button.classList.toggle('active', button.dataset.window === selectedPerformanceWindow);
  });

  if (curveTitleEl) {
    curveTitleEl.textContent = `${normalizeWindowLabel(selectedPerformanceWindow)}净值`;
  }

  if (todayEl) {
    animateKPIValue(todayEl, perf.today_return, formatPercent);
    todayEl.style.color = (Number(perf.today_return) || 0) >= 0 ? 'var(--green)' : 'var(--red)';
  }
  if (monthEl) {
    animateKPIValue(monthEl, perf.month_return, formatPercent);
    monthEl.style.color = (Number(perf.month_return) || 0) >= 0 ? 'var(--green)' : 'var(--red)';
  }
  if (drawdownEl) {
    animateKPIValue(drawdownEl, perf.max_drawdown, formatPercent);
  }

  if (rangeDataEl) {
    const windowReturn = perf.window_return;
    const sampleCount = perf.sample_count;
    const startDate = perf.start_date;
    const endDate = perf.end_date;
    if (windowReturn !== undefined && windowReturn !== null && sampleCount) {
      const returnClass = windowReturn >= 0 ? 'green' : 'red';
      const returnText = formatSignedRateValue(windowReturn);
      const startText = startDate ? formatDate(startDate) : '--';
      const endText = endDate ? formatDate(endDate) : '--';
      rangeDataEl.innerHTML = `
        <div class="range-card">
          <div class="range-card-head">
            <span class="range-card-label">${escapeHtml(normalizeWindowLabel(selectedPerformanceWindow))}收益</span>
            <span class="range-card-window">${escapeHtml(startText)} ~ ${escapeHtml(endText)}</span>
          </div>
          <div class="range-card-value ${returnClass}">${escapeHtml(returnText)}</div>
          <div class="range-card-sub">${escapeHtml(String(sampleCount))} 个交易日样本</div>
          ${insufficientDataWarningHtml(sampleCount, selectedPerformanceWindow)}
        </div>
      `;
    } else {
      const cards = toList(perf.comparison_cards);
      if (!cards.length) {
        rangeDataEl.innerHTML = '<span class="range-placeholder">当前区间暂无表现对比数据</span>';
      } else {
        rangeDataEl.innerHTML = cards.map(renderPerformanceCard).join('');
      }
    }
  }

  const canvas = document.getElementById('perf-nav-canvas');
  if (canvas && toList(perf.nav_curve).length > 0) {
    drawNavCurve(canvas, toList(perf.nav_curve));
  } else if (canvas) {
    drawNavCurve(canvas, []);
  }
}

function normalizeWindowLabel(window) {
  const normalized = normalizeText(window, '').toLowerCase();
  if (normalized === '7d') return '近 7 天';
  if (normalized === '30d') return '近 30 天';
  if (normalized === '90d') return '近 90 天';
  if (normalized === 'ytd') return '今年以来';
  return normalized.toUpperCase() || '--';
}

function resolvePerformanceCardLabel(card) {
  return normalizeText(pickFirst(card, ['label', 'title', 'name', 'metric']), '区间指标');
}

function formatSignedRateValue(raw) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  const pct = Math.abs(n) <= 1 ? n * 100 : n;
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct.toFixed(2)}%`;
}

function insufficientDataWarningHtml(sampleCount, window) {
  var expectedDays = { '7d': 7, '30d': 30, '90d': 90, 'ytd': 365 };
  var threshold = (expectedDays[window] || 30) * 0.8;
  if (!sampleCount || sampleCount >= threshold) return '';
  return '<div class="range-card-warning">⚠️ 数据不足 ' + (expectedDays[window] || 30) + ' 天，仅显示最近 ' + sampleCount + ' 天</div>';
}

function resolvePerformanceCardValue(card) {
  const raw = pickFirst(card, ['value', 'return', 'performance', 'metric_value'], null);
  return raw === null ? '--' : formatSignedRateValue(raw);
}

function renderPerformanceCard(card) {
  const valueRaw = Number(pickFirst(card, ['value', 'return', 'performance', 'metric_value'], NaN));
  const valueClass = Number.isFinite(valueRaw) ? (valueRaw > 0 ? 'green' : valueRaw < 0 ? 'red' : '') : '';
  const sub = normalizeText(pickFirst(card, ['description', 'subtitle', 'summary', 'note']), '区间收益与基准对比');
  const benchmarkLabel = normalizeText(pickFirst(card, ['benchmark_label', 'reference_label']), '基准');
  const benchmarkValue = pickFirst(card, ['benchmark_value', 'reference_value'], null);
  const excessValue = pickFirst(card, ['excess_return', 'spread', 'delta'], null);

  return `
    <div class="range-card">
      <div class="range-card-head">
        <span class="range-card-label">${escapeHtml(resolvePerformanceCardLabel(card))}</span>
        <span class="range-card-window">${escapeHtml(normalizeWindowLabel(selectedPerformanceWindow))}</span>
      </div>
      <div class="range-card-value ${valueClass}">${escapeHtml(resolvePerformanceCardValue(card))}</div>
      <div class="range-card-sub">${escapeHtml(sub)}</div>
      <div class="range-card-benchmark">
        <span>${escapeHtml(benchmarkLabel)} ${escapeHtml(benchmarkValue === null ? '--' : formatSignedRateValue(benchmarkValue))}</span>
        <span>超额 ${escapeHtml(excessValue === null ? '--' : formatSignedRateValue(excessValue))}</span>
      </div>
    </div>
  `;
}

function drawNavCurve(canvas, points) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, width, height);

  if (!points || points.length < 2) {
    ctx.fillStyle = 'rgba(120, 120, 120, 0.5)';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('暂无净值数据', width / 2, height / 2);
    return;
  }

  const navs = points.map(p => Number(p.nav) || 0);
  const min = Math.min(...navs);
  const max = Math.max(...navs);
  const range = max - min || 1;
  const topPadding = 16;
  const bottomPadding = 26;
  const leftPadding = 8;
  const rightPadding = 8;
  const plotWidth = width - leftPadding - rightPadding;
  const plotHeight = height - topPadding - bottomPadding;
  const isPositive = navs[navs.length - 1] >= navs[0];
  const lineColor = isPositive ? '#22c55e' : '#ef4444';

  ctx.strokeStyle = 'rgba(255,255,255,0.08)';
  ctx.lineWidth = 1;
  for (let i = 0; i < 3; i += 1) {
    const y = topPadding + (plotHeight / 2) * i;
    ctx.beginPath();
    ctx.moveTo(leftPadding, y);
    ctx.lineTo(width - rightPadding, y);
    ctx.stroke();
  }

  const coords = points.map((point, index) => {
    const x = leftPadding + (plotWidth * index) / (points.length - 1);
    const y = topPadding + plotHeight - (((Number(point.nav) || 0) - min) / range) * plotHeight;
    return { x, y, point };
  });

  const area = new Path2D();
  coords.forEach(({ x, y }, index) => {
    if (index === 0) area.moveTo(x, y);
    else area.lineTo(x, y);
  });
  area.lineTo(coords[coords.length - 1].x, height - bottomPadding + 4);
  area.lineTo(coords[0].x, height - bottomPadding + 4);
  area.closePath();
  const gradient = ctx.createLinearGradient(0, topPadding, 0, height - bottomPadding);
  gradient.addColorStop(0, isPositive ? 'rgba(34,197,94,0.24)' : 'rgba(239,68,68,0.2)');
  gradient.addColorStop(1, 'rgba(255,255,255,0)');
  const last = coords[coords.length - 1];
  var drawProgress = { value: 0 };
  var animDuration = 800;
  var animStart = performance.now();

  function animateCurve(currentTime) {
    var elapsed = currentTime - animStart;
    drawProgress.value = Math.min(elapsed / animDuration, 1);
    var eased = 1 - Math.pow(1 - drawProgress.value, 3);

    ctx.save();
    ctx.beginPath();
    ctx.rect(leftPadding, 0, plotWidth * eased, height);
    ctx.clip();

    ctx.fillStyle = gradient;
    ctx.fill(area);

    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2;
    ctx.beginPath();
    coords.forEach(function(coord, index) {
      if (index === 0) ctx.moveTo(coord.x, coord.y);
      else ctx.lineTo(coord.x, coord.y);
    });
    ctx.stroke();

    if (eased > 0.95) {
      ctx.fillStyle = lineColor;
      ctx.beginPath();
      ctx.arc(last.x, last.y, 3, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();

    if (drawProgress.value < 1) {
      requestAnimationFrame(animateCurve);
    }
  }
  requestAnimationFrame(animateCurve);

  ctx.fillStyle = 'rgba(231,237,245,0.72)';
  ctx.font = '10px SF Mono, ui-monospace, monospace';
  ctx.textAlign = 'left';
  ctx.fillText(`MAX ${max.toFixed(3)}`, leftPadding, 10);
  ctx.textAlign = 'right';
  ctx.fillText(`MIN ${min.toFixed(3)}`, width - rightPadding, 10);

  const startLabel = normalizeText(pickFirst(points[0], ['date', 'trade_date', 'timestamp']), '').slice(5) || '起点';
  const endLabel = normalizeText(pickFirst(points[points.length - 1], ['date', 'trade_date', 'timestamp']), '').slice(5) || '最新';
  ctx.textAlign = 'left';
  ctx.fillText(startLabel, leftPadding, height - 8);
  ctx.textAlign = 'right';
  ctx.fillText(endLabel, width - rightPadding, height - 8);
}

function renderAutomation(automation) {
  const auto = automation || {};
  const statusEl = document.getElementById('auto-status');
  const lastEl = document.getElementById('auto-last');
  const nextEl = document.getElementById('auto-next');
  if (statusEl) {
    statusEl.textContent = auto.today_status || 'pending';
    const s = String(auto.today_status || 'pending');
    statusEl.style.color = s === 'success' ? 'var(--green)' : s === 'failed' ? 'var(--red)' : 'var(--yellow)';
  }
  if (lastEl) {
    lastEl.textContent = auto.last_run_at ? formatTime(auto.last_run_at) : '尚未运行';
  }
  if (nextEl) {
    nextEl.textContent = auto.next_run_at ? formatTime(auto.next_run_at) : '等待调度';
  }
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
    const time = displayTimeValue(pickFirst(item, ['created_at', 'timestamp', 'time']));
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

function runSourceLabel(source) {
  const normalized = normalizeText(source, '').toLowerCase();
  if (normalized === 'manual') return '手动';
  if (normalized === 'auto') return '自动';
  if (normalized === 'backfill') return '回补';
  return normalizeText(source, '--');
}

function runStatusLabel(status) {
  const normalized = normalizeText(status, '').toLowerCase();
  if (normalized === 'completed' || normalized === 'success') return '已完成';
  if (normalized === 'running' || normalized === 'in_progress') return '运行中';
  if (normalized === 'accepted') return '已接受';
  if (normalized === 'failed' || normalized === 'error') return '失败';
  return normalizeText(status, '--');
}

function runStatusClass(status) {
  const normalized = normalizeText(status, '').toLowerCase();
  if (normalized === 'completed' || normalized === 'success') return 'ok';
  if (normalized === 'running' || normalized === 'in_progress' || normalized === 'accepted') return 'warn';
  if (normalized === 'failed' || normalized === 'error') return 'err';
  return 'info';
}

function formatSignedCurrency(raw) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  const sign = n > 0 ? '+' : '';
  return `${sign}CNY ${n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function getCaseCounts(snapshot) {
  const history = snapshot?.history || {};
  const latestRun = snapshot?.latest_run || {};
  const decisions = toList(history.decisions || latestRun.decision_items);
  const targets = toList(history.targets || latestRun.target_items);
  const orders = toList(history.orders || latestRun.order_items);
  const reconcile = toList(history.reconcile || latestRun.reconcile_items);
  const events = toList(history.events);
  const errors = events.filter(item => {
    const level = normalizeText(pickFirst(item, ['level', 'severity', 'event_type']), '').toLowerCase();
    return level === 'error' || level === 'err' || level === 'critical' || level === 'fatal';
  });
  const steps = toList(latestRun.steps);
  return {
    decisions,
    targets,
    orders,
    reconcile,
    events,
    errors,
    steps,
    decisionBuy: decisions.filter(item => normalizeText(pickFirst(item, ['action', 'parsed_action', 'signal']), '').toUpperCase() === 'BUY').length,
    decisionSell: decisions.filter(item => normalizeText(pickFirst(item, ['action', 'parsed_action', 'signal']), '').toUpperCase() === 'SELL').length,
    decisionHold: decisions.filter(item => normalizeText(pickFirst(item, ['action', 'parsed_action', 'signal']), '').toUpperCase() === 'HOLD').length,
  };
}

function buildRunMetaFromSnapshot(snapshot) {
  const latestRun = snapshot?.latest_run || {};
  const config = snapshot?.config || {};
  const history = snapshot?.history || {};
  const counts = getCaseCounts(snapshot);
  const runContextId = normalizeText(latestRun.run_context_id, '');
  return {
    id: runContextId || 'current-run',
    source: 'manual',
    market: normalizeText(snapshot?.market, document.getElementById('cfg-market')?.value || 'a'),
    status: normalizeText(latestRun.status, snapshot?.automation?.today_status || 'running'),
    trade_date: snapshot?.trade_date || null,
    created_at: latestRun.created_at || snapshot?.last_run_at || snapshot?.trade_date || null,
    finished_at: latestRun.finished_at || null,
    decision_mode: normalizeText(config.decision_mode, null),
    execution_mode: normalizeText(config.execution_mode, null),
    watchlist_count: toList(config.watchlist).length,
    decision_count: counts.decisions.length,
    target_count: counts.targets.length,
    order_count: counts.orders.length,
    net_pnl: latestRun.run_pnl_summary?.net_pnl ?? null,
    error_message: latestRun.error_message || latestRun.error || null,
    run_context_id: runContextId || null,
    supports_case_view: Boolean(runContextId),
    _counts: counts,
    _history: history,
    _latestRun: latestRun,
  };
}

function buildRunMetaFromListItem(run) {
  return {
    id: run.id,
    source: run.source,
    market: run.market,
    status: run.status,
    trade_date: run.trade_date,
    created_at: run.created_at,
    finished_at: run.finished_at,
    decision_mode: run.decision_mode,
    execution_mode: run.execution_mode,
    watchlist_count: Number(run.watchlist_count || 0),
    decision_count: run.decision_count ?? null,
    target_count: run.target_count ?? null,
    order_count: run.order_count ?? null,
    net_pnl: run.net_pnl ?? null,
    error_message: run.error_message || null,
    run_context_id: run.run_context_id || null,
    supports_case_view: Boolean(run.supports_case_view),
  };
}

function mergeRunMeta(existing, incoming) {
  return {
    ...(existing || {}),
    ...(incoming || {}),
    id: normalizeText(incoming?.id || existing?.id, ''),
    run_context_id: incoming?.run_context_id || existing?.run_context_id || null,
    supports_case_view: Boolean(
      incoming?.supports_case_view ?? existing?.supports_case_view ?? incoming?.run_context_id ?? existing?.run_context_id
    ),
  };
}

function replaceHistoryRuns(runs) {
  historyRuns = toList(runs).map(buildRunMetaFromListItem);
}

function upsertHistoryRun(runMeta, options = {}) {
  const incoming = buildRunMetaFromListItem(runMeta);
  const next = [];
  let merged = false;
  historyRuns.forEach(run => {
    const sameId = normalizeText(run.id, '') === normalizeText(incoming.id, '');
    const sameContext = normalizeText(run.run_context_id, '') && normalizeText(run.run_context_id, '') === normalizeText(incoming.run_context_id, '');
    if (sameId || sameContext) {
      next.push(mergeRunMeta(run, incoming));
      merged = true;
    } else {
      next.push(run);
    }
  });
  if (!merged) {
    next.unshift(incoming);
    historyCounts.all += 1;
    if (incoming.source === 'manual') historyCounts.manual += 1;
    else if (incoming.source === 'auto') historyCounts.auto += 1;
  }
  historyRuns = next.sort((left, right) => {
    const leftTime = normalizeText(left.created_at, '');
    const rightTime = normalizeText(right.created_at, '');
    return rightTime.localeCompare(leftTime);
  });
  if (options.select) {
    selectedHistoryRunMeta = mergeRunMeta(selectedHistoryRunMeta, incoming);
  }
  renderRunCenter(historyRuns, { preserveData: true });
}

function stagePaneId(stage) {
  return `case-pane-${stage}`;
}

function renderCaseSummaryChips(meta, counts) {
  const chips = document.getElementById('case-summary-chips');
  if (!chips) return;
  const sourceLabel = runSourceLabel(meta?.source);
  const statusLabel = runStatusLabel(meta?.status);
  const pnlText = meta ? formatSignedCurrency(meta.net_pnl) : '--';
  const watchlistText = meta ? `${meta.watchlist_count ?? 0} 只` : '--';
  const decisionText = counts ? `${counts.decisions.length} 条` : '--';
  const targetText = counts ? `${counts.targets.length} 条` : '--';
  const orderText = counts ? `${counts.orders.length} 单` : '--';
  const errorText = counts ? `${counts.errors.length} 条` : '--';
  chips.innerHTML = `
    <span class="case-chip source">${escapeHtml(sourceLabel)}</span>
    <span class="case-chip status ${runStatusClass(meta?.status)}">${escapeHtml(statusLabel)}</span>
    <span class="case-chip">${escapeHtml(meta?.market || '--')}</span>
    <span class="case-chip">${escapeHtml(meta?.trade_date || '--')}</span>
    <span class="case-chip">${escapeHtml(watchlistText)}</span>
    <span class="case-chip">${escapeHtml(`决策 ${decisionText}`)}</span>
    <span class="case-chip">${escapeHtml(`目标 ${targetText}`)}</span>
    <span class="case-chip">${escapeHtml(`订单 ${orderText}`)}</span>
    <span class="case-chip">${escapeHtml(`异常 ${errorText}`)}</span>
    <span class="case-chip pnl">${escapeHtml(pnlText)}</span>
  `;
}

function renderCaseOverview(meta, snapshot) {
  const overviewGrid = document.getElementById('case-overview-grid');
  const overviewNote = document.getElementById('case-overview-note');
  const counts = getCaseCounts(snapshot);

  if (overviewGrid) {
    overviewGrid.innerHTML = `
      <div class="overview-card">
        <span class="overview-label">决策</span>
        <strong class="overview-value">${counts.decisions.length}</strong>
        <span class="overview-sub">${counts.decisionBuy} 买 / ${counts.decisionSell} 卖 / ${counts.decisionHold} 观望</span>
      </div>
      <div class="overview-card">
        <span class="overview-label">目标仓位</span>
        <strong class="overview-value">${counts.targets.length}</strong>
        <span class="overview-sub">配置输出的目标持仓</span>
      </div>
      <div class="overview-card">
        <span class="overview-label">订单</span>
        <strong class="overview-value">${counts.orders.length}</strong>
        <span class="overview-sub">执行链路中的订单</span>
      </div>
      <div class="overview-card">
        <span class="overview-label">对账</span>
        <strong class="overview-value">${counts.reconcile.length}</strong>
        <span class="overview-sub">持仓与行情校验结果</span>
      </div>
      <div class="overview-card">
        <span class="overview-label">异常</span>
        <strong class="overview-value">${counts.errors.length}</strong>
        <span class="overview-sub">需要关注的异常事件</span>
      </div>
      <div class="overview-card">
        <span class="overview-label">链路步数</span>
        <strong class="overview-value">${counts.steps.length}</strong>
        <span class="overview-sub">${snapshot?.latest_run?.status ? `最新状态: ${runStatusLabel(snapshot.latest_run.status)}` : '等待运行'}</span>
      </div>
    `;
  }

  if (overviewNote) {
    const latestStep = counts.steps[counts.steps.length - 1];
    const latestMessage = normalizeText(latestStep?.message || latestStep?.summary || snapshot?.latest_run?.message, '');
    overviewNote.innerHTML = latestMessage
      ? `最近一步：<strong>${escapeHtml(latestMessage)}</strong>`
      : (meta?.supports_case_view ? '点击阶段按钮查看决策、订单、目标仓位、对账和异常的明细。' : '自动运行只展示概要，不提供完整案件视图。');
  }
}

function renderCaseStageRail(meta, snapshot) {
  const rail = document.getElementById('case-stage-rail');
  if (!rail) return;
  const counts = getCaseCounts(snapshot);
  const stageButtons = [
    { stage: 'overview', label: '概览', count: counts.steps.length },
    { stage: 'decisions', label: '决策', count: counts.decisions.length },
    { stage: 'targets', label: '目标仓位', count: counts.targets.length },
    { stage: 'orders', label: '订单', count: counts.orders.length },
    { stage: 'reconcile', label: '对账', count: counts.reconcile.length },
    { stage: 'errors', label: '异常', count: counts.errors.length },
  ];
  rail.innerHTML = stageButtons.map(item => {
    const active = selectedCaseStage === stagePaneId(item.stage) || (!selectedCaseStage && item.stage === 'overview');
    const disabled = !meta?.supports_case_view && item.stage !== 'overview';
    return `<button type="button" class="${active ? 'active' : ''}" ${disabled ? 'disabled' : ''} onclick="switchTab(this,'${stagePaneId(item.stage)}')">
      <span>${escapeHtml(item.label)}</span>
      <strong>${escapeHtml(String(item.count))}</strong>
    </button>`;
  }).join('');
}

function renderCaseStageVisibility() {
  const panes = document.querySelectorAll('.case-stage-pane');
  panes.forEach(pane => {
    const shouldShow = pane.id === selectedCaseStage || (!selectedCaseStage && pane.id === stagePaneId('overview'));
    pane.classList.toggle('active', shouldShow);
  });
}

function renderCaseEmptyState(message) {
  selectedHistoryRunMeta = null;
  selectedCaseSnapshot = null;
  selectedCaseStage = stagePaneId('overview');
  const titleEl = document.getElementById('case-title');
  const subtitleEl = document.getElementById('case-subtitle');
  const noteEl = document.getElementById('case-overview-note');
  const gridEl = document.getElementById('case-overview-grid');
  if (titleEl) titleEl.textContent = '请选择运行记录';
  if (subtitleEl) subtitleEl.textContent = message || '从上方运行中心选择一条记录，查看完整案件视图。';
  if (noteEl) noteEl.textContent = message || '从上方运行中心选择一条记录，查看完整案件视图。';
  if (gridEl) {
    gridEl.innerHTML = `
      <div class="overview-empty">
        <strong>暂无案件</strong>
        <span>选择一条手动运行记录后，这里会显示链路时间线和阶段明细。</span>
      </div>
    `;
  }
  const chips = document.getElementById('case-summary-chips');
  if (chips) chips.innerHTML = '';
  const rail = document.getElementById('case-stage-rail');
  if (rail) rail.innerHTML = '';
  renderDecisions([]);
  renderOrders([]);
  renderTargets([]);
  renderErrorEvents([]);
  renderReconcile([]);
  renderTimeline({ steps: [] });
  renderRunPnlSummary({});
  renderCaseStageVisibility();
}

function renderCaseSnapshot(meta, snapshot) {
  syncSnapshotCollectionsFromSteps(snapshot);
  const titleEl = document.getElementById('case-title');
  const subtitleEl = document.getElementById('case-subtitle');
  const counts = getCaseCounts(snapshot);
  const latestRun = snapshot?.latest_run || {};
  const statusLabel = runStatusLabel(meta?.status || latestRun.status);
  const sourceLabel = runSourceLabel(meta?.source);
  const runId = meta?.run_context_id || meta?.id || latestRun.run_context_id || '--';
  if (titleEl) {
    titleEl.textContent = `${sourceLabel} · ${runId}`;
  }
  if (subtitleEl) {
    const duration = meta?.created_at && meta?.finished_at ? `${formatTime(meta.created_at)} → ${formatTime(meta.finished_at)}` : formatTime(meta?.created_at);
    subtitleEl.textContent = `${statusLabel} · ${meta?.market || '--'} · ${meta?.trade_date || '--'} · ${duration}`;
  }

  renderCaseSummaryChips(meta, counts);
  renderCaseOverview(meta, snapshot);
  renderCaseStageRail(meta, snapshot);
  renderCaseStageVisibility();

  const pnlSummary = latestRun.run_pnl_summary || {
    net_pnl: meta?.net_pnl,
    execution_fee_total: null,
    unrealized_pnl: null,
  };
  renderRunPnlSummary(pnlSummary);
  renderTimeline(latestRun);
  renderDecisions(counts.decisions);
  renderOrders(counts.orders);
  renderTargets(counts.targets);
  renderErrorEvents(counts.events);
  renderReconcile(counts.reconcile);
}

function renderActiveCase() {
  if (!selectedHistoryRunMeta) {
    renderCaseEmptyState();
    return;
  }
  if (!selectedHistoryRunMeta.supports_case_view) {
    const meta = selectedHistoryRunMeta;
    const titleEl = document.getElementById('case-title');
    const subtitleEl = document.getElementById('case-subtitle');
    const noteEl = document.getElementById('case-overview-note');
    const gridEl = document.getElementById('case-overview-grid');
    if (titleEl) titleEl.textContent = `${runSourceLabel(meta.source)} · ${meta.id}`;
    if (subtitleEl) subtitleEl.textContent = `${runStatusLabel(meta.status)} · 自动运行仅保留概要`;
    if (noteEl) noteEl.textContent = meta.error_message || '自动运行没有完整案件链路，只有概要卡片。';
    if (gridEl) {
      gridEl.innerHTML = `
        <div class="overview-card">
          <span class="overview-label">状态</span>
          <strong class="overview-value">${escapeHtml(runStatusLabel(meta.status))}</strong>
          <span class="overview-sub">自动运行概要</span>
        </div>
        <div class="overview-card">
          <span class="overview-label">观察列表</span>
          <strong class="overview-value">${meta.watchlist_count ?? 0}</strong>
          <span class="overview-sub">仅记录列表规模</span>
        </div>
        <div class="overview-card">
          <span class="overview-label">净值</span>
          <strong class="overview-value">${escapeHtml(formatSignedCurrency(meta.net_pnl))}</strong>
          <span class="overview-sub">历史运行摘要</span>
        </div>
        <div class="overview-empty">
          <strong>自动运行</strong>
          <span>没有可展开的案件细节，切换到手动运行可以查看完整链路。</span>
        </div>
      `;
    }
    const chips = document.getElementById('case-summary-chips');
    if (chips) {
      chips.innerHTML = `
        <span class="case-chip source">${escapeHtml(runSourceLabel(meta.source))}</span>
        <span class="case-chip status ${runStatusClass(meta.status)}">${escapeHtml(runStatusLabel(meta.status))}</span>
        <span class="case-chip">${escapeHtml(meta.market || '--')}</span>
        <span class="case-chip">${escapeHtml(meta.trade_date || '--')}</span>
        <span class="case-chip">${escapeHtml(`观察 ${meta.watchlist_count ?? 0} 只`)}</span>
        <span class="case-chip pnl">${escapeHtml(formatSignedCurrency(meta.net_pnl))}</span>
      `;
    }
    const rail = document.getElementById('case-stage-rail');
    if (rail) {
      rail.innerHTML = `
        <button type="button" class="active" onclick="switchTab(this,'${stagePaneId('overview')}')">概览 <strong>1</strong></button>
      `;
    }
    selectedCaseStage = stagePaneId('overview');
    renderCaseStageVisibility();
    renderDecisions([]);
    renderOrders([]);
    renderTargets([]);
    renderErrorEvents([]);
    renderReconcile([]);
    renderTimeline({ steps: [] });
    renderRunPnlSummary({ net_pnl: meta.net_pnl });
    return;
  }
  if (!selectedCaseSnapshot) {
    const meta = selectedHistoryRunMeta;
    const emptySnapshot = { latest_run: { steps: [] }, history: {} };
    const titleEl = document.getElementById('case-title');
    const subtitleEl = document.getElementById('case-subtitle');
    if (titleEl) titleEl.textContent = `${runSourceLabel(meta.source)} · ${meta.id}`;
    if (subtitleEl) subtitleEl.textContent = '案件快照加载中...';
    renderCaseSummaryChips(meta, getCaseCounts(emptySnapshot));
    renderCaseOverview(meta, emptySnapshot);
    renderCaseStageRail(meta, emptySnapshot);
    selectedCaseStage = stagePaneId('overview');
    renderCaseStageVisibility();
    renderDecisions([]);
    renderOrders([]);
    renderTargets([]);
    renderErrorEvents([]);
    renderReconcile([]);
    renderTimeline({ steps: [] });
    renderRunPnlSummary({ net_pnl: meta.net_pnl });
    return;
  }
  renderCaseSnapshot(selectedHistoryRunMeta, selectedCaseSnapshot);
}

function deriveHistoryFromSteps(steps) {
  const collections = {
    decisions: [],
    targets: [],
    orders: [],
    reconcile: [],
  };
  toList(steps).forEach(step => {
    const stage = normalizeText(step?.stage || step?.name, '').toLowerCase();
    const items = toList(step?.items);
    if (!items.length) return;
    if (stage === 'decision') collections.decisions = items;
    if (stage === 'target') collections.targets = items;
    if (stage === 'execute') collections.orders = items;
    if (stage === 'reconcile') collections.reconcile = items;
  });
  return collections;
}

function syncSnapshotCollectionsFromSteps(snapshot) {
  if (!snapshot || typeof snapshot !== 'object') return;
  const latestRun = snapshot.latest_run || {};
  const derived = deriveHistoryFromSteps(latestRun.steps);
  snapshot.history = snapshot.history || {};
  if (derived.decisions.length && !toList(snapshot.history.decisions).length) snapshot.history.decisions = derived.decisions;
  if (derived.targets.length && !toList(snapshot.history.targets).length) snapshot.history.targets = derived.targets;
  if (derived.orders.length && !toList(snapshot.history.orders).length) snapshot.history.orders = derived.orders;
  if (derived.reconcile.length && !toList(snapshot.history.reconcile).length) snapshot.history.reconcile = derived.reconcile;
}

function activateLiveRunCase(runContextId) {
  const watchlistValue = document.getElementById('cfg-watchlist')?.value || '';
  selectedHistoryRunMeta = {
    id: runContextId,
    source: 'manual',
    market: document.getElementById('cfg-market')?.value || 'a',
    status: 'running',
    trade_date: document.getElementById('inner-trade-date')?.textContent || null,
    created_at: new Date().toISOString(),
    finished_at: null,
    decision_mode: document.getElementById('cfg-mode')?.value || null,
    execution_mode: execMode,
    watchlist_count: watchlistValue.split(',').map(s => s.trim()).filter(Boolean).length,
    decision_count: 0,
    target_count: 0,
    order_count: 0,
    net_pnl: null,
    error_message: null,
    run_context_id: runContextId,
    supports_case_view: true,
  };
  selectedCaseSnapshot = {
    latest_run: {
      run_context_id: runContextId,
      status: 'running',
      steps: [],
      message: '运行已提交，等待策略引擎接收。',
    },
    history: {},
  };
  selectedCaseStage = stagePaneId('overview');
  upsertHistoryRun(selectedHistoryRunMeta, { select: true });
  openCaseDrawer(runContextId);
  renderActiveCase();
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

function renderRunPnlSummary(summary) {
  const pnl = summary || {};
  const net = pnl.net_pnl === null || pnl.net_pnl === undefined || pnl.net_pnl === '' ? null : Number(pnl.net_pnl);
  const fee = pnl.execution_fee_total === null || pnl.execution_fee_total === undefined || pnl.execution_fee_total === '' ? null : Number(pnl.execution_fee_total);
  const unrealized = pnl.unrealized_pnl === null || pnl.unrealized_pnl === undefined || pnl.unrealized_pnl === '' ? null : Number(pnl.unrealized_pnl);

  const netEl = document.getElementById('run-pnl-net');
  const feeEl = document.getElementById('run-pnl-fee');
  const unrealizedEl = document.getElementById('run-pnl-unrealized');

  if (netEl) {
    netEl.textContent = net === null || Number.isNaN(net) ? '--' : formatSignedCurrency(net);
    netEl.className = `run-pnl-value ${net > 0 ? 'green' : net < 0 ? 'red' : ''}`;
  }
  if (feeEl) {
    feeEl.textContent = fee === null || Number.isNaN(fee) ? '--' : formatSignedCurrency(fee);
    feeEl.className = fee && fee > 0 ? 'run-pnl-value red' : 'run-pnl-value';
  }
  if (unrealizedEl) {
    unrealizedEl.textContent = unrealized === null || Number.isNaN(unrealized) ? '--' : formatSignedCurrency(unrealized);
    unrealizedEl.className = `run-pnl-value ${unrealized > 0 ? 'green' : unrealized < 0 ? 'red' : ''}`;
  }
}

function renderReconcile(list) {
  const rows = toList(list);
  const tb = document.getElementById('tb-reconcile');
  if (!tb) return;
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="8" style="color:var(--dim)">暂无数据</td></tr>';
    return;
  }
  tb.innerHTML = rows.map(item => {
    const symbol = normalizeText(item.symbol);
    const quantity = normalizeText(item.quantity);
    const avgCost = formatCurrency(item.avg_cost);
    const markPrice = formatCurrency(item.mark_price);
    const changeValue = Number(item.change_pct);
    const change = formatPercent(item.change_pct);
    const pnl = formatCurrency(item.unrealized_pnl);
    const fee = formatCurrency(item.fee_total);
    const markTime = formatTime(item.mark_time);
    const pnlValue = Number(item.unrealized_pnl);
    const pnlClass = pnlValue > 0 ? 'green' : pnlValue < 0 ? 'red' : '';
    const changeClass = Number.isFinite(changeValue) ? (changeValue > 0 ? 'green' : changeValue < 0 ? 'red' : '') : '';
    return `<tr>
      <td>
        <div class="reconcile-symbol">
          <strong>${escapeHtml(symbol)}</strong>
          <span>${escapeHtml(markTime === '--' ? '行情时间待更新' : `行情 ${markTime}`)}</span>
        </div>
      </td>
      <td><div class="cell-stack"><span class="cell-primary">${escapeHtml(quantity)}</span><span class="cell-secondary">持仓数量</span></div></td>
      <td><div class="cell-stack"><span class="cell-primary">${escapeHtml(avgCost)}</span><span class="cell-secondary">成本价</span></div></td>
      <td><div class="cell-stack"><span class="cell-primary">${escapeHtml(markPrice)}</span><span class="cell-secondary">现价</span></div></td>
      <td class="reconcile-move ${changeClass}">${escapeHtml(change)}</td>
      <td class="${pnlClass}">${escapeHtml(pnl)}</td>
      <td>${escapeHtml(fee)}</td>
      <td>${escapeHtml(markTime)}</td>
    </tr>`;
  }).join('');
}

function stageBodyHtml(step) {
  if (!step || typeof step !== 'object') return '';
  const stage = normalizeText(step.stage || step.name, '').toLowerCase();
  if (stage === 'reconcile' && toList(step.items).length) {
    return toList(step.items).map(item => {
      return `<tr><td>${escapeHtml(normalizeText(item.symbol))}</td><td>${escapeHtml(formatCurrency(item.avg_cost))}</td><td>${escapeHtml(formatCurrency(item.mark_price))}</td><td>${escapeHtml(formatPercent(item.change_pct))}</td><td>${escapeHtml(formatCurrency(item.unrealized_pnl))}</td></tr>`;
    }).join('');
  }
  return legacyStageBodyHtml(step);
}

const legacyStageBodyHtml = function(step) {
  if (!step || typeof step !== 'object') return '';
  const stage = normalizeText(step.stage || step.name, '').toLowerCase();
  const items = toList(step.items);
  if (items.length) {
    const first = items[0] || {};
    if (first.target_position_ratio !== undefined || first.target_weight !== undefined) {
      return toList(items).map(item => {
        const symbol = escapeHtml(normalizeText(pickFirst(item, ['symbol', 'stock_code'])));
        const quantity = escapeHtml(normalizeText(pickFirst(item, ['target_quantity', 'quantity', 'target_value'])));
        const weight = escapeHtml(formatPercent(pickFirst(item, ['target_weight', 'target_position_ratio'], null)));
        return `<tr><td>${symbol}</td><td>${quantity}</td><td>${weight}</td></tr>`;
      }).join('');
    }
    if (first.status !== undefined || first.limit_price !== undefined || first.quantity !== undefined) {
      return toList(items).map(item => {
        const symbol = escapeHtml(normalizeText(pickFirst(item, ['symbol', 'stock_code'])));
        const action = escapeHtml(normalizeText(pickFirst(item, ['action', 'parsed_action']), '--').toUpperCase());
        const qty = escapeHtml(normalizeText(pickFirst(item, ['quantity', 'qty']), '--'));
        const status = escapeHtml(normalizeText(item.status, '--').toUpperCase());
        return `<tr><td>${symbol}</td><td>${action}</td><td>${qty}</td><td>${status}</td></tr>`;
      }).join('');
    }
    return toList(items).map(item => {
      const symbol = escapeHtml(normalizeText(pickFirst(item, ['symbol', 'stock_code'])));
      const action = normalizeText(pickFirst(item, ['action', 'parsed_action', 'signal']), '--').toUpperCase();
      const confidence = escapeHtml(formatConfidence(item.confidence));
      const badgeClass = action === 'BUY' ? 'badge-buy' : action === 'SELL' ? 'badge-sell' : 'badge-hold';
      return `<tr><td>${symbol}</td><td><span class="badge ${badgeClass}">${escapeHtml(action)}</span></td><td>${confidence}</td></tr>`;
    }).join('');
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
  const timeline = document.getElementById('case-timeline');
  if (!timeline) return;
  const steps = toList(latestRun?.steps);
  const traceId = document.getElementById('run-trace-id');
  if (traceId) traceId.textContent = latestRun?.run_context_id || '--';
  if (!steps.length) {
    timeline.innerHTML = '<div class="timeline-empty" id="timeline-empty">选择一条运行记录查看链路时间线</div>';
    return;
  }
  const lastStep = steps[steps.length - 1];
  const currentStatus = normalizeText(lastStep?.status || latestRun?.status, 'done').toLowerCase();
  const doneCount = steps.filter(step => normalizeText(step?.status, '').toLowerCase() === 'done').length;
  timeline.innerHTML = `
    <div class="timeline-summary">
      <div class="timeline-stat">
        <span class="timeline-stat-label">阶段累计</span>
        <span class="timeline-stat-value">${escapeHtml(String(steps.length))}</span>
      </div>
      <div class="timeline-stat">
        <span class="timeline-stat-label">已完成</span>
        <span class="timeline-stat-value">${escapeHtml(String(doneCount))}</span>
      </div>
      <div class="timeline-stat">
        <span class="timeline-stat-label">当前状态</span>
        <span class="timeline-stat-value ${currentStatus === 'failed' || currentStatus === 'error' ? 'error' : currentStatus === 'running' || currentStatus === 'in_progress' ? 'running' : ''}">${escapeHtml(runStatusLabel(currentStatus))}</span>
      </div>
    </div>
  `;
  steps.forEach(step => {
    if (!step) return;
    const stage = normalizeText(step.stage || step.name, 'stage').toLowerCase();
    const statusRaw = normalizeText(step.status, 'done').toLowerCase();
    const status = statusRaw === 'error' || statusRaw === 'failed' ? 'error' : statusRaw === 'running' || statusRaw === 'in_progress' ? 'running' : 'done';
    const time = formatTime(pickFirst(step, ['created_at', 'timestamp', 'time']));
    const duration = step.duration_ms != null ? ` · ${step.duration_ms}ms` : '';
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
        <span class="step-time">${escapeHtml(`${time}${duration}`)}</span>
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
  const snapshotRunId = normalizeText(data.latest_run?.run_context_id, '');
  const activeRunId = normalizeText(selectedHistoryRunMeta?.run_context_id, '');
  const preserveActiveCase = Boolean(
    !simRunning
    && selectedHistoryRunMeta
    && (
      selectedHistoryRunMeta.supports_case_view === false
      || (activeRunId && snapshotRunId && activeRunId !== snapshotRunId)
    )
  );

  // Apply server-side pagination metadata
  const p = data.pagination || {};
  if (p.decisions) { pag.decisions.total = p.decisions.total; pag.decisions.totalPages = p.decisions.total_pages; }
  if (p.orders) { pag.orders.total = p.orders.total; pag.orders.totalPages = p.orders.total_pages; }
  if (p.targets) { pag.targets.total = p.targets.total; pag.targets.totalPages = p.targets.total_pages; }

  renderRisk(data.risk || {}, data.history?.targets || []);
  renderPerformance(data.performance || {});
  renderAutomation(data.automation || {});
  renderAlerts(data.risk?.alerts || []);
  if (!preserveActiveCase) {
    const snapshotMeta = data.latest_run?.run_context_id ? buildRunMetaFromSnapshot(data) : null;
    if (snapshotMeta) {
      selectedHistoryRunMeta = selectedHistoryRunMeta
        ? { ...selectedHistoryRunMeta, ...snapshotMeta }
        : snapshotMeta;
      selectedCaseSnapshot = data;
      renderActiveCase();
    } else if (!selectedHistoryRunMeta) {
      renderCaseEmptyState();
    }
  }
}

async function loadDashboard() {
  const market = document.getElementById('cfg-market')?.value || 'a';
  if (historyPanelMarket !== market) {
    historyPanelMarket = market;
    historyPanelNextCursor = null;
    historyPanelHasMore = false;
    historyPanelLimit = 0;
  }
  try {
    setPanelLoading('all');
    const panelLoads = [
      Promise.resolve().then(() => loadPerformancePanel(market)),
      Promise.resolve().then(() => loadAutomationPanel(market)),
      Promise.resolve().then(() => loadHistoryPanel(market)),
    ];
    const [workbenchRes, killStatusRes] = await Promise.all([
      fetch(`${WORKBENCH_API}?market=${market}&account_kind=auto`),
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

    document.querySelectorAll('.run-btn, .save-btn').forEach(addRippleToButton);

    Promise.allSettled(panelLoads).then(() => { clearPanelLoading(); });

    await refreshMarketQuotes();
  } catch (error) {
    clearPanelLoading();
    addAlert('err', `数据加载失败: ${error.message}`);
  }
}

function showPerformanceLoading() {
  var canvas = document.getElementById('perf-nav-canvas');
  var rangeData = document.getElementById('range-data');
  if (canvas) {
    var ctx = canvas.getContext('2d');
    var dpr = window.devicePixelRatio || 1;
    canvas.width = canvas.clientWidth * dpr;
    canvas.height = canvas.clientHeight * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, canvas.clientWidth, canvas.clientHeight);
    ctx.fillStyle = 'rgba(120, 120, 120, 0.5)';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('加载中...', canvas.clientWidth / 2, canvas.clientHeight / 2);
  }
  if (rangeData) {
    rangeData.innerHTML = '<span class="range-placeholder">加载中...</span>';
  }
}

async function loadPerformancePanel(market, window) {
  const win = window || selectedPerformanceWindow || '7d';
  selectedPerformanceWindow = win;
  showPerformanceLoading();
  try {
    const res = await fetch(`${PERFORMANCE_API}?market=${market}&account_kind=auto&window=${win}`);
    if (!res.ok) return;
    const data = await parseResponseBody(res);
    renderPerformance(data);
  } catch (_) {}
}

async function loadAutomationPanel(market) {
  try {
    const res = await fetch(`${AUTOMATION_API}?market=${market}&account_kind=auto`);
    if (!res.ok) return;
    const data = await parseResponseBody(res);
    renderAutomation(data);
  } catch (_) {}
}

async function loadHistoryPanel(market, options = {}) {
  historyPanelLoading = true;
  historyPanelMarket = market || historyPanelMarket || 'a';
  const append = Boolean(options.append);
  try {
    let url = `${HISTORY_API}?market=${historyPanelMarket}&account_kind=auto&source=all&limit=${HISTORY_PANEL_BATCH}`;
    if (append && historyPanelNextCursor) {
      url += `&cursor=${encodeURIComponent(historyPanelNextCursor)}`;
    }
    const res = await fetch(url);
    if (!res.ok) return;
    const data = await parseResponseBody(res);
    const runs = toList(data.runs);
    historyPanelHasMore = Boolean(data.has_more);
    historyPanelNextCursor = data.next_cursor || null;
    if (data.total_count != null) {
      historyCounts = {
        all: Number(data.total_count) || 0,
        manual: Number(data.manual_count) || 0,
        auto: Number(data.auto_count) || 0,
      };
    }
    if (append) {
      const existingKeys = new Set(historyRuns.map(r => `${r.created_at || ''}::${r.id}`));
      const newRuns = runs.filter(r => !existingKeys.has(`${r.created_at || ''}::${r.id}`));
      historyRuns = historyRuns.concat(newRuns.map(buildRunMetaFromListItem));
    } else {
      replaceHistoryRuns(runs);
    }
    renderRunCenter(historyRuns, { preserveData: true });
  } catch (_) {
  } finally {
    historyPanelLoading = false;
    renderRunCenter(historyRuns, { preserveData: true });
  }
}

function getFilteredHistoryRuns() {
  if (selectedHistorySource === 'manual') return historyRuns.filter(run => run.source === 'manual');
  if (selectedHistorySource === 'auto') return historyRuns.filter(run => run.source === 'auto');
  return historyRuns.slice();
}

function renderRunFilterButton(source, label, count) {
  const active = selectedHistorySource === source;
  return `<button type="button" class="pill-btn ${active ? 'active' : ''}" data-history-source="${escapeHtml(source)}" onclick="setHistoryFilter('${source}', this)">
    <span>${escapeHtml(label)}</span>
    <strong>${escapeHtml(String(count))}</strong>
  </button>`;
}

function renderRunCard(run) {
  const active = selectedHistoryRunMeta && normalizeText(selectedHistoryRunMeta.id, '') === normalizeText(run.id, '');
  const statusClass = runStatusClass(run.status);
  const netPnl = formatSignedCurrency(run.net_pnl);
  const pnlClass = run.net_pnl > 0 ? 'green' : (run.net_pnl < 0 ? 'red' : '');
  const details = [
    run.trade_date || '--',
    run.market || '--',
    run.supports_case_view ? '完整案件' : '概要',
  ];
  const counts = [
    `决策 ${run.decision_count ?? 0}`,
    `目标 ${run.target_count ?? 0}`,
    `订单 ${run.order_count ?? 0}`,
    `观察 ${run.watchlist_count ?? 0}`,
  ];
  const note = normalizeText(run.error_message, '');
  const hint = run.supports_case_view
    ? '<div class="run-card-hint"><span class="hint-icon">👁</span><span class="hint-text">点击查看案件详情</span></div>'
    : '';
  return `
    <button type="button" class="run-card ${active ? 'active' : ''}" data-run-id="${escapeHtml(run.id)}" onclick="selectHistoryRun('${escapeHtml(run.id)}')">
      <div class="run-card-head">
        <span class="run-card-source ${run.source}">${escapeHtml(runSourceLabel(run.source))}</span>
        <span class="run-card-status ${statusClass}">${escapeHtml(runStatusLabel(run.status))}</span>
      </div>
      <div class="run-card-title">${escapeHtml(run.id)}</div>
      <div class="run-card-meta">
        ${details.map(item => `<span>${escapeHtml(item)}</span>`).join('')}
      </div>
      <div class="run-card-badges">
        ${counts.map(item => `<span class="run-mini-chip">${escapeHtml(item)}</span>`).join('')}
        <span class="run-mini-chip pnl ${pnlClass}">${escapeHtml(netPnl)}</span>
      </div>
      <div class="run-card-note ${note ? 'show' : ''}">${escapeHtml(note || (run.decision_mode ? `${run.decision_mode} · ${run.execution_mode || '--'}` : ''))}</div>
      ${hint}
    </button>
  `;
}

let _historyScrollObserver = null;

function setupHistoryScrollObserver(footerEl) {
  if (!_historyScrollObserver) {
    _historyScrollObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && historyPanelHasMore && !historyPanelLoading) {
          loadMoreHistoryRuns();
        }
      });
    }, { rootMargin: '100px' });
  }
  _historyScrollObserver.disconnect();
  if (footerEl) {
    _historyScrollObserver.observe(footerEl);
  }
}

var RUN_CARD_ITEM_HEIGHT = 72;
var RUN_CARD_VIRTUAL_THRESHOLD = 50;

function renderRunCenterVirtual(runs, options) {
  var list = document.getElementById('run-center-list');
  if (!list) return renderRunCenter(runs, options);
  if (runs.length < RUN_CARD_VIRTUAL_THRESHOLD) {
    return renderRunCenter(runs, options);
  }
  var buffer = 4;
  var itemHeight = RUN_CARD_ITEM_HEIGHT;
  var totalHeight = Math.ceil(runs.length / 2) * itemHeight;
  var scrollTop = list.scrollTop;
  var viewportHeight = list.clientHeight;
  var startRow = Math.max(0, Math.floor(scrollTop / itemHeight) - buffer);
  var endRow = Math.min(
    Math.ceil(runs.length / 2),
    Math.ceil((scrollTop + viewportHeight) / itemHeight) + buffer
  );
  var visibleRuns = runs.slice(startRow * 2, endRow * 2);
  var paddingTop = startRow * itemHeight;
  var paddingBottom = totalHeight - endRow * itemHeight;

  if (!options.preserveData) {
    replaceHistoryRuns(runs);
  }
  var filtered = getFilteredHistoryRuns().filter(function(run) {
    var idx = runs.findIndex(function(r) { return r.id === run.id; });
    return idx >= startRow * 2 && idx < endRow * 2;
  });
  list.innerHTML =
    '<div style="height:' + paddingTop + 'px"></div>' +
    filtered.map(renderRunCard).join('') +
    '<div style="height:' + paddingBottom + 'px"></div>';
  if (selectedHistoryRunMeta) {
    list.querySelectorAll('.run-card').forEach(function(card) {
      if (card.dataset.runId === selectedHistoryRunMeta.id) {
        card.classList.add('active');
      }
    });
  }
}

function renderRunCenter(runs, options = {}) {
  if (!options.preserveData) {
    replaceHistoryRuns(runs);
  }
  const filtered = getFilteredHistoryRuns();
  const filters = document.getElementById('run-history-filters');
  const list = document.getElementById('run-center-list');
  const footer = document.getElementById('run-center-footer');
  const counts = {
    all: historyCounts.all || historyRuns.length,
    manual: historyCounts.manual || historyRuns.filter(run => run.source === 'manual').length,
    auto: historyCounts.auto || historyRuns.filter(run => run.source === 'auto').length,
  };
  if (filters) {
    filters.innerHTML = [
      renderRunFilterButton('all', '全部', counts.all),
      renderRunFilterButton('manual', '手动', counts.manual),
      renderRunFilterButton('auto', '自动', counts.auto),
    ].join('');
  }

  if (!selectedHistoryRunMeta && filtered.length) {
    selectHistoryRun(filtered[0].id, { fromRender: true });
  }

  if (!list) return;
  if (!filtered.length) {
    list.innerHTML = '<div class="run-center-empty">没有符合当前筛选条件的运行记录</div>';
    if (footer) footer.innerHTML = '';
    if (!selectedHistoryRunMeta) {
      renderCaseEmptyState('当前筛选下没有可用的运行记录。');
    }
    return;
  }

  list.innerHTML = filtered.map(renderRunCard).join('');
  if (footer) {
    const totalCount = historyCounts.all || historyRuns.length;
    footer.innerHTML = historyPanelHasMore
      ? `<button type="button" class="run-load-more" id="run-history-load-more" onclick="loadMoreHistoryRuns()" ${historyPanelLoading ? 'disabled' : ''}>${historyPanelLoading ? '加载中...' : '加载更多 (已显示 ' + totalCount + ' 条)'}</button>`
      : `<div class="run-center-status">已显示全部 ${totalCount} 条记录</div>`;
    setupHistoryScrollObserver(footer);
  }
  if (selectedHistoryRunMeta) {
    const current = filtered.find(run => normalizeText(run.id, '') === normalizeText(selectedHistoryRunMeta.id, ''));
    if (!current) {
      list.querySelectorAll('.run-card').forEach(card => card.classList.remove('active'));
    }
  }
}

function setHistoryFilter(source) {
  selectedHistorySource = source || 'all';
  renderRunCenter(historyRuns, { preserveData: true });
}

function loadMoreHistoryRuns() {
  if (historyPanelLoading || !historyPanelHasMore) return;
  loadHistoryPanel(historyPanelMarket || (document.getElementById('cfg-market')?.value || 'a'), { append: true });
}

async function selectHistoryRun(runId, options = {}) {
  const run = historyRuns.find(item => normalizeText(item.id, '') === normalizeText(runId, ''));
  if (!run) return;

  selectedHistoryRunMeta = { ...run };
  selectedCaseStage = stagePaneId('overview');
  renderRunCenter(historyRuns, { preserveData: true });
  openCaseDrawer(runId);

  if (!run.supports_case_view || !run.run_context_id) {
    selectedCaseSnapshot = null;
    hideCaseDrawerSkeleton();
    renderActiveCase();
    return;
  }

  const token = ++historySnapshotToken;
  selectedCaseSnapshot = null;
  hideCaseDrawerSkeleton();
  renderActiveCase();
  try {
    const res = await fetch(`${WORKBENCH_API}?run_context_id=${encodeURIComponent(run.run_context_id)}`);
    const body = await parseResponseBody(res);
    if (!res.ok) {
      throw new Error(extractErrorMessage(body, `运行快照加载失败 (${res.status})`));
    }
    if (token !== historySnapshotToken) return;
    selectedCaseSnapshot = body;
    syncSnapshotCollectionsFromSteps(selectedCaseSnapshot);
    selectedHistoryRunMeta = mergeRunMeta(selectedHistoryRunMeta, buildRunMetaFromSnapshot(body));
    upsertHistoryRun(selectedHistoryRunMeta, { select: true });
    hideCaseDrawerSkeleton();
    renderActiveCase();
  } catch (error) {
    if (token !== historySnapshotToken) return;
    selectedCaseSnapshot = null;
    hideCaseDrawerSkeleton();
    renderCaseEmptyState(error.message);
  }
}

function setPanelLoading(panel) {
  const loaders = {
    'perf-today': '--', 'perf-month': '--', 'perf-drawdown': '--',
    'auto-status': '...', 'auto-last': '...', 'auto-next': '...',
  };
  if (panel === 'all' || panel === 'perf') {
    Object.entries(loaders).forEach(([id, val]) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    });
  }
}

function clearPanelLoading() {}

function buildRunPayload() {
  const watchlist = document.getElementById('cfg-watchlist').value
    .split(',')
    .map(s => s.trim())
    .filter(Boolean);
  return {
    market: document.getElementById('cfg-market').value,
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
const SCAN_US_API = '/api/v1/dashboard/scan-us';

async function triggerScan() {
  if (scanRunning) return;
  scanRunning = true;
  const btn = document.getElementById('scan-btn');
  const market = document.getElementById('cfg-market').value;
  const isUS = market === 'us';
  setButtonLoading(btn, true, '扫描中...');
  document.getElementById('scan-content').innerHTML = '<span style="color:var(--yellow)">正在扫描' + (isUS ? '美股' : 'A股') + '全市场，请稍候...</span>';

  try {
    const api = isUS ? SCAN_US_API : SCAN_API;
    const res = await fetch(api, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ top_n: 10 }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || '扫描失败');
    renderScanResult(body, isUS);
  } catch (e) {
    document.getElementById('scan-content').innerHTML = `<span style="color:var(--red)">扫描失败: ${escapeHtml(e.message)}</span>`;
  } finally {
    scanRunning = false;
    const btn = document.getElementById('scan-btn');
    setButtonLoading(btn, false, '全市场扫描');
  }
}

function renderScanResult(data, isUS) {
  const area = document.getElementById('scan-content');
  if (data.status === 'no_catalog') {
    area.innerHTML = '<span style="color:var(--yellow)">股票列表不可用，请检查网络</span>';
    return;
  }

  const marketLabel = isUS ? '美股' : 'A股';
  let html = `<div class="scan-summary">已扫描 ${data.total_scanned} 只${marketLabel}股票</div>`;

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
        market: document.getElementById('cfg-market').value,
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

// ── 观察列表同步 ──

function isUSSymbol(symbol) {
  return !symbol.endsWith('.SH') && !symbol.endsWith('.SZ');
}

function filterWatchlistByMarket() {
  var market = document.getElementById('cfg-market').value;
  var watchlistEl = document.getElementById('cfg-watchlist');
  if (!watchlistEl) return;

  var symbols = watchlistEl.value.split(',').map(s => s.trim()).filter(Boolean);
  var filtered = symbols.filter(function(s) {
    return market === 'us' ? isUSSymbol(s) : !isUSSymbol(s);
  });

  watchlistEl.value = filtered.join(',');
}

function addToWorkspaceWatchlist(symbol, name) {
  var watchlistEl = document.getElementById('cfg-watchlist');
  if (!watchlistEl) return false;

  var market = document.getElementById('cfg-market').value;
  var isUS = isUSSymbol(symbol);
  
  // 检查是否与当前市场匹配
  if (market === 'us' && !isUS) {
    showToast(symbol + ' 是A股股票，请切换到A股市场', 'info');
    return false;
  }
  if (market === 'a' && isUS) {
    showToast(symbol + ' 是美股股票，请切换到美股市场', 'info');
    return false;
  }

  var current = watchlistEl.value.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
  if (current.indexOf(symbol) !== -1) {
    showToast(symbol + ' 已在观察列表中', 'info');
    return false;
  }

  current.push(symbol);
  watchlistEl.value = current.join(',');
  showToast(symbol + ' 已添加到观察列表', 'success');
  return true;
}
