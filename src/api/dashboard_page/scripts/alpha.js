// Alpha 持仓助手
const ALPHA_REPORT_API = '/api/v1/alpha/portfolio/report';
const ALPHA_HOLDINGS_API = '/api/v1/alpha/holdings';
const VALID_REPORT_ACTIONS = ['HOLD', 'ADD', 'REDUCE', 'EXIT', 'WATCH'];

let alphaPortfolioSymbols = [];
let alphaEditingHoldingId = null;

function alphaActionClass(action) {
  const normalized = String(action || 'HOLD').toLowerCase();
  if (normalized === 'buy') return 'buy';
  if (normalized === 'sell') return 'sell';
  return 'hold';
}

function alphaReportActionLabel(action) {
  const normalized = String(action || '').toUpperCase();
  switch (normalized) {
    case 'HOLD':
      return '继续持有';
    case 'ADD':
      return '加仓观察';
    case 'REDUCE':
      return '减仓';
    case 'EXIT':
      return '止损/退出';
    case 'WATCH':
      return '观察';
    default:
      return action || '--';
  }
}

function parseAlphaReportSymbols(raw) {
  return Array.from(new Set(String(raw || '')
    .split(/[,\s]+/)
    .map((value) => value.trim().toUpperCase())
    .filter(Boolean)));
}

function createAlphaLotRow(lot = {}) {
  return `<div class="alpha-lot-row" data-alpha-lot-row>
    <div class="alpha-lot-index">批次</div>
    <label class="alpha-field">
      <span>买入日期</span>
      <input type="date" data-alpha-lot-buy-date value="${escapeHtml(lot.buy_date || '')}" />
    </label>
    <label class="alpha-field">
      <span>买入价格</span>
      <input type="number" min="0" step="0.0001" data-alpha-lot-buy-price value="${escapeHtml(lot.buy_price ?? '')}" placeholder="如 18.56" />
    </label>
    <label class="alpha-field">
      <span>数量</span>
      <input type="number" min="0" step="0.0001" data-alpha-lot-quantity value="${escapeHtml(lot.quantity ?? '')}" placeholder="如 200" />
    </label>
    <button type="button" class="alpha-builder-remove alpha-builder-remove-lot" data-alpha-remove-lot>删除批次</button>
  </div>`;
}

function createAlphaStockCard(position = {}) {
  const symbol = String(position.symbol || '').trim().toUpperCase();
  const lots = Array.isArray(position.lots) && position.lots.length ? position.lots : [{}];
  return `<article class="alpha-stock-card" data-alpha-stock-card>
    <div class="alpha-stock-card-head">
      <label class="alpha-field alpha-stock-symbol-field">
        <span>股票代码</span>
        <input data-alpha-symbol value="${escapeHtml(symbol)}" placeholder="如 MU / 600519 / 000001.SZ" />
      </label>
      <button type="button" class="alpha-builder-remove alpha-builder-remove-stock" data-alpha-remove-stock>删除股票</button>
    </div>
    <div class="alpha-stock-card-lots" data-alpha-lots>
      ${lots.map((lot) => createAlphaLotRow(lot)).join('')}
    </div>
    <div class="alpha-stock-card-actions">
      <button type="button" class="alpha-builder-add-lot" data-alpha-add-lot>新增批次</button>
    </div>
  </article>`;
}

function appendAlphaStockCard(position = {}) {
  const root = document.getElementById('alpha-stock-cards');
  if (!root) return;
  root.insertAdjacentHTML('beforeend', createAlphaStockCard(position));
}

function ensureAlphaAnalysisBuilder() {
  const root = document.getElementById('alpha-stock-cards');
  if (!root) return;
  if (!root.querySelector('[data-alpha-stock-card]')) {
    appendAlphaStockCard();
  }
}

function collectAlphaReportPositions() {
  const cards = Array.from(document.querySelectorAll('[data-alpha-stock-card]'));
  return cards.map((card) => {
    const symbol = String(card.querySelector('[data-alpha-symbol]')?.value || '').trim().toUpperCase();
    const lots = Array.from(card.querySelectorAll('[data-alpha-lot-row]')).map((row) => {
      const buyDate = String(row.querySelector('[data-alpha-lot-buy-date]')?.value || '').trim();
      const buyPrice = String(row.querySelector('[data-alpha-lot-buy-price]')?.value || '').trim();
      const quantity = String(row.querySelector('[data-alpha-lot-quantity]')?.value || '').trim();
      if (!buyDate && !buyPrice && !quantity) {
        return null;
      }
      return {
        buy_date: buyDate || null,
        buy_price: buyPrice === '' ? null : Number(buyPrice),
        quantity: quantity === '' ? null : Number(quantity),
      };
    }).filter(Boolean);
    return { symbol, lots };
  }).filter((position) => position.symbol);
}

function collectAlphaHoldingEntries() {
  return collectAlphaReportPositions().flatMap((position) => position.lots.map((lot) => ({
    symbol: position.symbol,
    buy_date: lot.buy_date,
    buy_price: lot.buy_price,
    quantity: lot.quantity,
  }))).filter((entry) => entry.symbol && entry.buy_date && Number(entry.buy_price) > 0 && Number(entry.quantity) > 0);
}

function resetAlphaBuilder(positions = [{}]) {
  const root = document.getElementById('alpha-stock-cards');
  if (!root) return;
  root.innerHTML = '';
  positions.forEach((position) => appendAlphaStockCard(position));
  ensureAlphaAnalysisBuilder();
  const saveButton = document.getElementById('alpha-analysis-save');
  if (saveButton) {
    delete saveButton.dataset.alphaEditEntryId;
  }
}

function beginAlphaHoldingEdit(entry) {
  alphaEditingHoldingId = entry.entry_id;
  resetAlphaBuilder([{
    symbol: entry.symbol,
    lots: [{
      buy_date: entry.buy_date,
      buy_price: entry.buy_price,
      quantity: entry.quantity,
    }],
  }]);
  const saveButton = document.getElementById('alpha-analysis-save');
  if (saveButton) {
    saveButton.dataset.alphaEditEntryId = entry.entry_id;
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
    <div class="alpha-position-item" data-symbol="${escapeHtml(item.symbol)}">
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
        <div class="alpha-fill-meta">${escapeHtml(normalizeText(fill.executed_at || fill.created_at, '--'))}</div>
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
  alphaPortfolioSymbols = positions
    .map((item) => String(item?.symbol || '').trim().toUpperCase())
    .filter(Boolean);
  renderAlphaHoldingsSummary(snapshot, positions, fills);
  renderAlphaPositions(positions);
  renderAlphaFillHistory(fills);
  renderAlphaMultiLegHistory(fills);
}

function renderAlphaSavedHoldings(items) {
  const root = document.getElementById('alpha-holdings-records');
  if (!root) return;
  if (!items.length) {
    root.innerHTML = '<div class="alpha-empty-state">暂无已保存买入记录</div>';
    return;
  }
  root.innerHTML = items.map((item) => `
    <div class="alpha-fill-row" data-alpha-saved-holding-id="${escapeHtml(item.entry_id)}">
      <div>
        <div class="alpha-fill-symbol">${escapeHtml(item.symbol)}</div>
        <div class="alpha-fill-meta">${escapeHtml(item.buy_date)} / ${escapeHtml(formatNumber(item.buy_price, 4))} / ${escapeHtml(formatNumber(item.quantity, 4))}</div>
      </div>
      <div class="alpha-stock-card-actions">
        <button type="button" class="alpha-builder-add-lot" data-alpha-history-edit data-alpha-edit-entry="${escapeHtml(item.entry_id)}">编辑</button>
        <button type="button" class="alpha-builder-remove" data-alpha-history-delete data-alpha-delete-entry="${escapeHtml(item.entry_id)}">删除</button>
      </div>
    </div>
  `).join('');
}

async function loadAlphaWorkbench() {
  const res = await fetch(WORKBENCH_API);
  if (!res.ok) {
    throw new Error('alpha workbench load failed');
  }
  const data = await res.json();
  renderAlphaPortfolio(data.alpha?.portfolio || {});
}

async function loadAlphaSavedHoldings() {
  const res = await fetch(ALPHA_HOLDINGS_API);
  if (!res.ok) {
    throw new Error('alpha holdings load failed');
  }
  const data = await res.json();
  renderAlphaSavedHoldings(toList(data.items));
  return toList(data.items);
}

function renderAlphaReport(report, requestedSymbols = []) {
  const body = document.getElementById('alpha-report-body');
  if (!body) return;
  const items = toList(report?.items);
  if (!items.length) {
    const emptyNote = requestedSymbols.length
      ? `未返回 ${requestedSymbols.join(', ')} 的分析结果。请检查输入股票代码，或留空走当前持仓分析。`
      : '当前无持仓可分析';
    body.innerHTML = `<div class="alpha-report-empty">${escapeHtml(emptyNote)}</div>`;
    return;
  }
  const windowLabel = normalizeText(report?.backtest_window, '60d');
  const list = items.map((item) => {
    const symbol = normalizeText(item.symbol, '--');
    const analysisContext = item.analysis_context || {};
    const position = item.position || item;
    const shadow = item.shadow || {};
    const backtest = item.backtest || {};
    const recommendation = item.recommendation || {};
    const riskNotes = toList(item.risk_notes);

    const action = String(recommendation.action || 'WATCH').toUpperCase();
    const actionClass = VALID_REPORT_ACTIONS.includes(action) ? action.toLowerCase() : 'watch';
    const actionLabel = alphaReportActionLabel(action);
    const recConfidence = formatConfidence(recommendation.confidence);
    const shadowAction = String(shadow.action || 'UNKNOWN').toUpperCase();
    const shadowConfidence = formatConfidence(shadow.confidence);

    const quantity = normalizeText(position.quantity, '--');
    const avgCost = formatNumber(position.avg_cost, 4);
    const markPrice = formatNumber(position.mark_price, 4);
    const pnl = Number(position.unrealized_pnl);
    const pnlClass = Number.isFinite(pnl) && pnl >= 0 ? 'green' : 'red';
    const pnlText = formatCurrency(pnl);

    const btStatus = normalizeText(backtest.status, 'no_data');
    const btScore = normalizeText(backtest.score, 'N/A');
    const recReason = normalizeText(recommendation.reason, '无明确建议');
    const lotCount = Number(analysisContext.lot_count || 0);
    const totalInputQuantity = analysisContext.total_quantity == null
      ? '--'
      : formatNumber(analysisContext.total_quantity, 4);
    const latestBuyDate = normalizeText(analysisContext.last_buy_date, '--');
    const firstBuyDate = normalizeText(analysisContext.first_buy_date, '--');
    const weightedBuyPrice = analysisContext.weighted_avg_cost == null
      ? '--'
      : formatNumber(analysisContext.weighted_avg_cost, 4);
    const totalInputCost = analysisContext.total_cost == null
      ? '--'
      : formatCurrency(analysisContext.total_cost);

    let riskNotesHtml = '';
    if (riskNotes.length) {
      riskNotesHtml = `<ul>${riskNotes
        .map((note) => `<li>${escapeHtml(String(note))}</li>`)
        .join('')}</ul>`;
    }

    return `<div class="alpha-report-item" data-symbol="${escapeHtml(symbol)}">
      <div class="alpha-report-item-head">
        <span class="alpha-report-symbol">${escapeHtml(symbol)}</span>
        <span class="alpha-report-recommendation ${actionClass}">${escapeHtml(actionLabel)}</span>
      </div>
      <div class="alpha-report-grid">
        <span class="alpha-report-grid-label">当前仓位</span><span class="alpha-report-grid-value">${escapeHtml(quantity)}</span>
        <span class="alpha-report-grid-label">成本</span><span class="alpha-report-grid-value">${escapeHtml(avgCost)}</span>
        <span class="alpha-report-grid-label">现价</span><span class="alpha-report-grid-value">${escapeHtml(markPrice)}</span>
        <span class="alpha-report-grid-label">浮盈</span><span class="alpha-report-grid-value ${pnlClass}">${escapeHtml(pnlText)}</span>
      </div>
      <div class="alpha-report-grid">
        <span class="alpha-report-grid-label">买入批次</span><span class="alpha-report-grid-value">${escapeHtml(String(lotCount || 0))}</span>
        <span class="alpha-report-grid-label">累计数量</span><span class="alpha-report-grid-value">${escapeHtml(String(totalInputQuantity))}</span>
        <span class="alpha-report-grid-label">累计投入</span><span class="alpha-report-grid-value">${escapeHtml(totalInputCost)}</span>
        <span class="alpha-report-grid-label">加权均价</span><span class="alpha-report-grid-value">${escapeHtml(weightedBuyPrice)}</span>
      </div>
      <div class="alpha-report-grid">
        <span class="alpha-report-grid-label">首次买入</span><span class="alpha-report-grid-value">${escapeHtml(firstBuyDate)}</span>
        <span class="alpha-report-grid-label">最近买入</span><span class="alpha-report-grid-value">${escapeHtml(latestBuyDate)}</span>
        <span class="alpha-report-grid-label">模拟建议</span><span class="alpha-report-grid-value">${escapeHtml(shadowAction)} (${escapeHtml(shadowConfidence)})</span>
        <span class="alpha-report-grid-label">综合建议</span><span class="alpha-report-grid-value">${escapeHtml(actionLabel)} (${escapeHtml(recConfidence)})</span>
      </div>
      <div class="alpha-report-backtest">
        <span>回测 (${escapeHtml(windowLabel)}): ${escapeHtml(btStatus)}</span>
        <span class="alpha-report-score">${escapeHtml(btScore)}</span>
      </div>
      <div class="alpha-report-risk">
        <strong>${escapeHtml(actionLabel)}:</strong> ${escapeHtml(recReason)}
        ${riskNotesHtml}
      </div>
    </div>`;
  }).join('');
  body.innerHTML = `<div class="alpha-report-list">${list}</div>`;
}

function showAlphaReportLoading() {
  const body = document.getElementById('alpha-report-body');
  if (!body) return;
  body.innerHTML = '<div class="alpha-report-loading">正在生成持仓分析报告…</div>';
}

async function loadAlphaReport() {
  const windowSelect = document.getElementById('alpha-report-window');
  const shadowToggle = document.getElementById('alpha-report-include-shadow');
  const backtestToggle = document.getElementById('alpha-report-include-backtest');
  const body = document.getElementById('alpha-report-body');
  if (!body) return;
  const positions = collectAlphaReportPositions();
  const requestedSymbols = positions.length
    ? positions.map((position) => position.symbol)
    : alphaPortfolioSymbols;

  const payload = {
    positions: positions,
    symbols: requestedSymbols,
    include_shadow: shadowToggle?.checked !== false,
    include_backtest: backtestToggle?.checked !== false,
    backtest_window: windowSelect?.value || '60d',
    opening_cash: 10000,
  };

  const btn = document.getElementById('alpha-report-generate');
  if (btn) btn.disabled = true;
  showAlphaReportLoading();

  try {
    const res = await fetch(ALPHA_REPORT_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await parseResponseBody(res);
    if (!res.ok) {
      throw new Error(extractErrorMessage(data, `报告生成失败 (${res.status})`));
    }
    renderAlphaReport(data, requestedSymbols);
  } catch (error) {
    body.innerHTML = `<div class="alpha-report-empty" style="color:var(--danger)">报告生成失败: ${escapeHtml(error.message)}</div>`;
    addAlert('err', `持仓分析报告失败: ${error.message}`);
  } finally {
    if (btn) btn.disabled = false;
  }
}

document.getElementById('alpha-report-generate')?.addEventListener('click', loadAlphaReport);
document.getElementById('alpha-add-stock-card')?.addEventListener('click', () => appendAlphaStockCard());
document.getElementById('alpha-analysis-builder')?.addEventListener('click', (event) => {
  const trigger = event.target.closest('button');
  if (!trigger) return;
  if (trigger.matches('[data-alpha-add-lot]')) {
    const stockCard = trigger.closest('[data-alpha-stock-card]');
    const lotsRoot = stockCard?.querySelector('[data-alpha-lots]');
    if (lotsRoot) {
      lotsRoot.insertAdjacentHTML('beforeend', createAlphaLotRow());
    }
    return;
  }
  if (trigger.matches('[data-alpha-remove-lot]')) {
    const stockCard = trigger.closest('[data-alpha-stock-card]');
    const lots = stockCard?.querySelectorAll('[data-alpha-lot-row]') || [];
    if (lots.length > 1) {
      trigger.closest('[data-alpha-lot-row]')?.remove();
    }
    return;
  }
  if (trigger.matches('[data-alpha-remove-stock]')) {
    const cards = document.querySelectorAll('[data-alpha-stock-card]');
    if (cards.length > 1) {
      trigger.closest('[data-alpha-stock-card]')?.remove();
    }
  }
});

async function updateAlphaHolding(entryId, payload) {
  const res = await fetch(`${ALPHA_HOLDINGS_API}/${encodeURIComponent(entryId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await parseResponseBody(res);
  if (!res.ok) {
    throw new Error(extractErrorMessage(data, `更新失败 (${res.status})`));
  }
  return data;
}

async function deleteAlphaHolding(entryId) {
  const res = await fetch(`${ALPHA_HOLDINGS_API}/${encodeURIComponent(entryId)}`, {
    method: 'DELETE',
  });
  const data = await parseResponseBody(res);
  if (!res.ok) {
    throw new Error(extractErrorMessage(data, `删除失败 (${res.status})`));
  }
  alphaEditingHoldingId = null;
  resetAlphaBuilder();
  await loadAlphaSavedHoldings();
  await loadAlphaWorkbench();
  await loadAlphaReport();
  return data;
}

async function saveAlphaHoldings() {
  const btn = document.getElementById('alpha-analysis-save');
  const editingEntryId = btn?.dataset?.alphaEditEntryId || alphaEditingHoldingId;
  if (btn) {
    btn.disabled = true;
    btn.textContent = '保存中...';
  }

  const entries = collectAlphaHoldingEntries();

  try {
    if (!entries.length) {
      throw new Error('请至少填写一条有效的买入记录');
    }
    if (editingEntryId) {
      if (entries.length !== 1) {
        throw new Error('编辑模式一次只能保存一条记录');
      }
      await updateAlphaHolding(editingEntryId, entries[0]);
    } else {
      await Promise.all(entries.map(async (entry) => {
        const res = await fetch(ALPHA_HOLDINGS_API, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(entry),
        });
        const data = await parseResponseBody(res);
        if (!res.ok) {
          throw new Error(extractErrorMessage(data, `保存失败 (${res.status})`));
        }
      }));
    }
    alphaEditingHoldingId = null;
    resetAlphaBuilder();
    await loadAlphaSavedHoldings();
    await loadAlphaWorkbench();
    await loadAlphaReport();
    if (btn) {
      btn.textContent = '已保存';
      setTimeout(() => { btn.textContent = '保存'; btn.disabled = false; }, 2000);
    }
    showToast('持仓分析已保存', 'success');
  } catch (error) {
    if (btn) {
      btn.textContent = '保存失败';
      btn.disabled = false;
      setTimeout(() => { btn.textContent = '保存'; }, 2000);
    }
    showToast('保存失败: ' + error.message, 'error');
  }
}

document.getElementById('alpha-saved-holdings')?.addEventListener('click', async (event) => {
  const trigger = event.target.closest('button');
  if (!trigger) return;
  const entryId = trigger.getAttribute('data-alpha-edit-entry') || trigger.getAttribute('data-alpha-delete-entry');
  if (!entryId) return;
  const items = await loadAlphaSavedHoldings();
  const entry = items.find((item) => item.entry_id === entryId);
  if (trigger.matches('[data-alpha-history-edit]')) {
    if (entry) beginAlphaHoldingEdit(entry);
    return;
  }
  if (trigger.matches('[data-alpha-history-delete]')) {
    await deleteAlphaHolding(entryId);
  }
});

document.getElementById('alpha-analysis-save')?.addEventListener('click', saveAlphaHoldings);
ensureAlphaAnalysisBuilder();
loadAlphaSavedHoldings().catch((error) => console.error('加载已保存持仓失败:', error));
