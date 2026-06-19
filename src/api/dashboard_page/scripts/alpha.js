// Alpha 持仓助手
const ALPHA_ASSETS_API = '/api/v1/alpha/assets';
const ALPHA_TICKETS_API = '/api/v1/alpha/tickets';
const ALPHA_CAPABILITIES_API = '/api/v1/alpha/capabilities';
const ALPHA_PORTFOLIO_API = '/api/v1/alpha/portfolio';
const ALPHA_SCAN_API = '/api/v1/alpha/research/scan';
const ALPHA_PROPOSE_API = '/api/v1/alpha/research/propose-top-ticket';

let alphaTicketCache = [];

function alphaStatusMarkup(message, level = 'info') {
  const cssLevel = ['ok', 'warn', 'err'].includes(level) ? level : 'info';
  return `<span class="alpha-inline-status ${cssLevel}">${escapeHtml(message)}</span>`;
}

function alphaActionClass(action) {
  const normalized = String(action || 'HOLD').toLowerCase();
  if (normalized === 'buy') return 'buy';
  if (normalized === 'sell') return 'sell';
  return 'hold';
}

function alphaGuidanceLabel(guidance) {
  switch (guidance) {
    case 'new_position_candidate':
      return '新开仓';
    case 'add_or_watch':
      return '加仓观察';
    case 'reduce_or_exit':
      return '减仓/退出';
    case 'ignore_no_position':
      return '空仓忽略';
    default:
      return '继续观察';
  }
}

function groupAlphaFillsBySymbol(fills) {
  return fills.reduce((acc, fill) => {
    const symbol = fill.asset_symbol || fill.symbol || 'UNKNOWN';
    if (!acc[symbol]) {
      acc[symbol] = [];
    }
    acc[symbol].push(fill);
    return acc;
  }, {});
}

function renderAlphaExecutionCapability(capability) {
  const modeEl = document.getElementById('alpha-execution-mode');
  const reasonEl = document.getElementById('alpha-execution-reason');
  const dotEl = document.getElementById('alpha-cap-dot');
  const mode = normalizeText(capability?.mode, '--');
  if (modeEl) modeEl.textContent = mode;
  if (reasonEl) reasonEl.textContent = normalizeText(capability?.reason, '未配置执行能力');
  if (dotEl) {
    const normalized = mode.toLowerCase();
    dotEl.className = 'alpha-panel-dot' + (normalized === 'api' ? ' ok' : normalized === 'manual' ? ' warn' : ' err');
  }
}

function renderAlphaHoldingsSummary(snapshot, positions, fills) {
  const root = document.getElementById('alpha-holdings-summary');
  if (!root) return;
  const cards = [
    {
      label: '净值',
      value: snapshot ? formatCurrency(snapshot.nav) : '--',
      tone: 'neutral',
    },
    {
      label: '已实现盈亏',
      value: snapshot ? formatCurrency(snapshot.realized_pnl) : '--',
      tone: Number(snapshot?.realized_pnl || 0) >= 0 ? 'positive' : 'negative',
    },
    {
      label: '未实现盈亏',
      value: snapshot ? formatCurrency(snapshot.unrealized_pnl) : '--',
      tone: Number(snapshot?.unrealized_pnl || 0) >= 0 ? 'positive' : 'negative',
    },
    {
      label: '持仓 / 成交',
      value: `${positions.length} / ${fills.length}`,
      tone: 'neutral',
    },
  ];
  root.innerHTML = cards.map((card) => `
    <div class="alpha-summary-card">
      <div class="alpha-summary-label">${escapeHtml(card.label)}</div>
      <div class="alpha-summary-value ${card.tone}">${escapeHtml(card.value)}</div>
    </div>
  `).join('');
}

function renderAlphaPositions(positions) {
  const root = document.getElementById('alpha-positions');
  if (!root) return;
  if (!positions.length) {
    root.innerHTML = '<div class="alpha-empty-state">暂无持仓，先回填一次真实成交。</div>';
    return;
  }
  root.innerHTML = positions.map((item) => `
    <div class="alpha-position-item">
      <div>
        <div class="alpha-position-symbol">${escapeHtml(item.symbol)}</div>
        <div class="alpha-position-sub">${escapeHtml(String(item.quantity))} 股 / 均价 ${escapeHtml(formatNumber(item.avg_cost, 2))}</div>
      </div>
      <div class="alpha-position-metrics">
        <span>${escapeHtml(formatNumber(item.mark_price, 2))}</span>
        <span>${escapeHtml(formatCurrency((Number(item.mark_price) - Number(item.avg_cost)) * Number(item.quantity || 0)))}</span>
      </div>
    </div>
  `).join('');
}

function renderAlphaFillHistory(fills) {
  const root = document.getElementById('alpha-fill-history');
  if (!root) return;
  if (!fills.length) {
    root.innerHTML = '<div class="alpha-empty-state">暂无成交历史</div>';
    return;
  }
  root.innerHTML = fills.slice(0, 8).map((fill) => `
    <div class="alpha-fill-row">
      <div>
        <div class="alpha-fill-symbol">${escapeHtml(fill.asset_symbol || fill.ticket_id)}</div>
        <div class="alpha-fill-meta">${escapeHtml(normalizeText(fill.created_at, '--'))}</div>
      </div>
      <span class="alpha-ticket-action ${alphaActionClass(fill.action)}">${escapeHtml(normalizeText(fill.action, 'HOLD'))}</span>
      <div class="alpha-fill-value">${escapeHtml(String(fill.executed_quantity))} @ ${escapeHtml(formatNumber(fill.executed_price, 4))}</div>
    </div>
  `).join('');
}

function renderAlphaMultiLegHistory(fills) {
  const root = document.getElementById('alpha-multi-leg-history');
  if (!root) return;
  if (!fills.length) {
    root.innerHTML = '<div class="alpha-empty-state">暂无 multi-leg 记录</div>';
    return;
  }
  const grouped = groupAlphaFillsBySymbol(fills);
  root.innerHTML = Object.entries(grouped).map(([symbol, symbolFills]) => {
    const buyQty = symbolFills
      .filter((fill) => String(fill.action).toUpperCase() === 'BUY')
      .reduce((sum, fill) => sum + Number(fill.executed_quantity || 0), 0);
    const sellQty = symbolFills
      .filter((fill) => String(fill.action).toUpperCase() === 'SELL')
      .reduce((sum, fill) => sum + Number(fill.executed_quantity || 0), 0);
    return `
      <div class="alpha-leg-card">
        <div class="alpha-leg-symbol">${escapeHtml(symbol)}</div>
        <div class="alpha-leg-meta">成交 ${symbolFills.length} 笔</div>
        <div class="alpha-leg-stats">
          <span>买入 ${escapeHtml(formatNumber(buyQty, 4))}</span>
          <span>卖出 ${escapeHtml(formatNumber(sellQty, 4))}</span>
        </div>
      </div>
    `;
  }).join('');
}

function renderAlphaPortfolio(portfolio) {
  const snapshot = portfolio?.snapshot || null;
  const positions = toList(portfolio?.positions);
  const fills = toList(portfolio?.fills);
  renderAlphaHoldingsSummary(snapshot, positions, fills);
  renderAlphaPositions(positions);
  renderAlphaFillHistory(fills);
  renderAlphaMultiLegHistory(fills);
}

function renderAlphaExceptions(exceptions) {
  const root = document.getElementById('alpha-exceptions');
  const dotEl = document.getElementById('alpha-exc-dot');
  const panel = root?.closest('.alpha-panel');
  const isMismatch = exceptions?.latest_status === 'MISMATCH';
  if (!root) return;
  root.innerHTML = isMismatch
    ? `<div class="alpha-exception-json">${escapeHtml(JSON.stringify(exceptions.latest_discrepancies || {}))}</div>`
    : '<div class="alpha-ok-note">无异常</div>';
  if (dotEl) dotEl.className = 'alpha-panel-dot' + (isMismatch ? ' err' : ' ok');
  if (panel) panel.classList.toggle('alpha-has-exception', isMismatch);
}

function renderAlphaTickets(items) {
  const root = document.getElementById('alpha-tickets');
  const countEl = document.getElementById('alpha-ticket-count');
  alphaTicketCache = toList(items);
  if (countEl) countEl.textContent = String(alphaTicketCache.length);
  if (!root) return;
  if (!alphaTicketCache.length) {
    root.innerHTML = '<div class="alpha-empty-state">暂无建议单</div>';
    populateAlphaFillTicketSelect([]);
    return;
  }
  root.innerHTML = alphaTicketCache.map((item) => {
    const action = normalizeText(item.action, 'BUY').toUpperCase();
    const status = normalizeText(item.status, 'pending').toLowerCase();
    const qty = item.suggested_quantity ?? '--';
    const price = item.suggested_limit_price ?? '--';
    return `<div class="alpha-ticket-item">
      <div>
        <div class="alpha-ticket-symbol">${escapeHtml(item.asset_symbol)}</div>
        <div class="alpha-ticket-underlying">${escapeHtml(item.underlying_symbol || '')}</div>
      </div>
      <span class="alpha-ticket-action ${alphaActionClass(action)}">${escapeHtml(action)}</span>
      <span class="alpha-ticket-qty-price">${escapeHtml(String(qty))} @ ${escapeHtml(formatNumber(price, 4))}</span>
      <span class="alpha-ticket-status ${status}">${escapeHtml(status)}</span>
    </div>`;
  }).join('');
  populateAlphaFillTicketSelect(alphaTicketCache);
}

function populateAlphaFillTicketSelect(tickets) {
  const select = document.getElementById('alpha-fill-ticket');
  if (!select) return;
  if (!tickets.length) {
    select.innerHTML = '<option value="">暂无可回填建议单</option>';
    renderSelectedFillTicketMeta(null);
    return;
  }
  select.innerHTML = tickets.map((ticket) => `
    <option value="${escapeHtml(ticket.ticket_id)}">
      ${escapeHtml(ticket.asset_symbol)} · ${escapeHtml(String(ticket.action || 'BUY').toUpperCase())} · ${escapeHtml(String(ticket.suggested_quantity))}
    </option>
  `).join('');
  renderSelectedFillTicketMeta(tickets[0]);
}

function renderSelectedFillTicketMeta(ticket) {
  const meta = document.getElementById('alpha-fill-ticket-meta');
  if (!meta) return;
  if (!ticket) {
    meta.innerHTML = alphaStatusMarkup('先创建建议单，再回填成交。');
    return;
  }
  meta.innerHTML = `
    <div class="alpha-ticket-meta-row">
      <span>${escapeHtml(ticket.asset_symbol)}</span>
      <span>${escapeHtml(String(ticket.action || 'BUY').toUpperCase())}</span>
      <span>${escapeHtml(String(ticket.suggested_quantity || '--'))} @ ${escapeHtml(formatNumber(ticket.suggested_limit_price, 4))}</span>
    </div>
  `;
}

function handleAlphaFillTicketChange(event) {
  const ticketId = event?.target?.value;
  const ticket = alphaTicketCache.find((item) => item.ticket_id === ticketId) || null;
  renderSelectedFillTicketMeta(ticket);
  if (!ticket) return;
  const qtyEl = document.getElementById('alpha-fill-qty');
  const priceEl = document.getElementById('alpha-fill-price');
  if (qtyEl && !qtyEl.value) qtyEl.value = String(ticket.suggested_quantity || '');
  if (priceEl && !priceEl.value) priceEl.value = String(ticket.suggested_limit_price || '');
}

async function loadAlphaWorkbench() {
  const res = await fetch(WORKBENCH_API);
  if (!res.ok) {
    throw new Error('alpha workbench load failed');
  }
  const data = await res.json();
  renderAlphaTickets(data.alpha?.tickets || []);
  renderAlphaPortfolio(data.alpha?.portfolio || {});
  renderAlphaExceptions(data.alpha?.exceptions || {});
  renderAlphaWatchlist(data.alpha?.research?.watchlist || []);
  renderAlphaCandidates(data.alpha?.research?.latest_candidates || []);
  if (data.alpha?.execution_capability) {
    renderAlphaExecutionCapability(data.alpha.execution_capability);
  }
}

async function submitAlphaTicket(event) {
  event.preventDefault();
  try {
    const payload = {
      asset_symbol: document.getElementById('alpha-symbol').value.trim(),
      underlying_symbol: document.getElementById('alpha-underlying').value.trim(),
      action: 'BUY',
      thesis: document.getElementById('alpha-thesis').value.trim(),
      suggested_quantity: Number(document.getElementById('alpha-qty').value),
      suggested_limit_price: Number(document.getElementById('alpha-limit').value),
      expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
    };
    const response = await fetch(ALPHA_TICKETS_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const body = await parseResponseBody(response);
      throw new Error(extractErrorMessage(body, '创建建议单失败'));
    }
    event.target.reset();
    await loadAlphaWorkbench();
  } catch (error) {
    console.error('Failed to submit alpha ticket:', error);
    alert('创建建议单失败: ' + error.message);
  }
}

async function submitAlphaManualFill(event) {
  event.preventDefault();
  const statusRoot = document.getElementById('alpha-fill-status');
  try {
    const ticketId = document.getElementById('alpha-fill-ticket').value.trim();
    const payload = {
      operator_id: document.getElementById('alpha-fill-operator').value.trim(),
      executed_quantity: Number(document.getElementById('alpha-fill-qty').value),
      executed_price: Number(document.getElementById('alpha-fill-price').value),
      notes: document.getElementById('alpha-fill-notes').value.trim(),
    };
    if (!ticketId) {
      throw new Error('请先选择建议单');
    }
    const res = await fetch(`${ALPHA_TICKETS_API}/${encodeURIComponent(ticketId)}/fills`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const body = await parseResponseBody(res);
    if (!res.ok) {
      throw new Error(extractErrorMessage(body, '记录成交失败'));
    }
    if (statusRoot) {
      statusRoot.innerHTML = alphaStatusMarkup('成交已记录，正在刷新持仓视图。', 'ok');
    }
    event.target.reset();
    await loadAlphaWorkbench();
  } catch (error) {
    console.error('Failed to submit alpha manual fill:', error);
    if (statusRoot) {
      statusRoot.innerHTML = alphaStatusMarkup(error.message, 'err');
    } else {
      alert('记录成交失败: ' + error.message);
    }
  }
}

async function loadAlphaAssets() {
  try {
    const res = await fetch(ALPHA_ASSETS_API);
    if (!res.ok) return;
    const data = await res.json();
    const root = document.getElementById('alpha-assets');
    if (!root) return;
    if (!data.items || data.items.length === 0) {
      root.innerHTML = '<div class="alpha-empty-state">暂无资产</div>';
      return;
    }
    root.innerHTML = data.items.map((asset) => {
      const ms = (asset.market_status || '').toLowerCase();
      const msClass = ms === 'active' || ms === 'open' || ms === 'trading'
        ? 'active'
        : ms === 'suspended' || ms === 'halted'
          ? 'suspended'
          : 'inactive';
      return `<div class="alpha-asset-item">
        <span class="alpha-asset-symbol">${escapeHtml(asset.symbol)}</span>
        <span class="alpha-asset-underlying">${escapeHtml(asset.underlying_symbol)}</span>
        <span class="alpha-asset-badge ${msClass}">${escapeHtml(asset.market_status || '--')}</span>
        <span class="alpha-asset-badge ${msClass}">${escapeHtml(asset.asset_status || '--')}</span>
      </div>`;
    }).join('');
  } catch (error) {
    console.error('加载Alpha资产失败:', error);
  }
}

async function loadAlphaTickets() {
  try {
    await loadAlphaWorkbench();
  } catch (error) {
    console.error('加载Alpha工作台失败:', error);
  }
}

function renderAlphaWatchlist(items) {
  const root = document.getElementById('alpha-watchlist');
  if (!root) return;
  if (!items.length) {
    root.innerHTML = '<div class="alpha-empty-state">暂无观察标的</div>';
    return;
  }
  root.innerHTML = items.map((item) => `<div class="alpha-watch-item">
    <span class="alpha-watch-symbol">${escapeHtml(item.symbol)}</span>
    <span class="alpha-watch-underlying">${escapeHtml(item.underlying_symbol)}</span>
    <span class="alpha-watch-priority">P${escapeHtml(String(item.priority))}</span>
  </div>`).join('');
}

function renderAlphaCandidates(items) {
  const root = document.getElementById('alpha-candidates');
  if (!root) return;
  if (!items.length) {
    root.innerHTML = '<div class="alpha-empty-state">暂无候选标的</div>';
    return;
  }
  root.innerHTML = items.map((item) => {
    const action = normalizeText(item.action, 'HOLD');
    const actionClass = alphaActionClass(action);
    const guidance = alphaGuidanceLabel(item.portfolio_guidance);
    const heldHint = item.is_held ? `持仓 ${formatNumber(item.held_quantity, 4)}` : '空仓';
    return `<div class="alpha-candidate-item alpha-candidate-rich">
      <div>
        <div class="alpha-candidate-symbol">${escapeHtml(item.symbol)}</div>
        <div class="alpha-candidate-guidance">${escapeHtml(guidance)} · ${escapeHtml(heldHint)}</div>
      </div>
      <span class="alpha-candidate-action ${actionClass}">${escapeHtml(action)}</span>
      <div class="alpha-candidate-metrics">
        <span class="alpha-candidate-score">${Number(item.score || 0).toFixed(4)}</span>
        <span class="alpha-candidate-guidance-tag">${escapeHtml(guidance)}</span>
      </div>
    </div>`;
  }).join('');
}

async function runAlphaScan() {
  const root = document.getElementById('alpha-candidates');
  if (root) {
    root.innerHTML = '<div class="alpha-empty-state" style="color:var(--yellow)">扫描中...</div>';
  }
  try {
    const res = await fetch(ALPHA_SCAN_API, { method: 'POST' });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || '扫描失败');
    renderAlphaCandidates(body.items || []);
  } catch (error) {
    if (root) {
      root.innerHTML = `<div class="alpha-empty-state" style="color:var(--red)">扫描失败: ${escapeHtml(error.message)}</div>`;
    }
  }
}

async function proposeTopAlphaTicket() {
  try {
    const res = await fetch(ALPHA_PROPOSE_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thesis_prefix: 'dashboard auto' }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || '生成建议单失败');
    await loadAlphaWorkbench();
  } catch (error) {
    console.error('生成建议单失败:', error);
    alert('生成建议单失败: ' + error.message);
  }
}
