// Alpha 持仓助手
const ALPHA_ANALYSIS_RUNS_API = '/api/v1/alpha/analysis-runs';
const ALPHA_HOLDINGS_API = '/api/v1/alpha/holdings';
const ALPHA_HOLDINGS_SUMMARY_API = '/api/v1/alpha/holdings/summary';

let alphaEditingHoldingId = null;
let currentMarket = 'a';
let alphaHoldingsEntriesCache = [];
let alphaPositionsBySymbol = {};
let alphaHoldingsSummaryCache = { summary: [] };
let alphaEditingSymbol = null;
let alphaEditingEntryIds = [];
let alphaAnalysisRunsCursor = null;
let alphaAnalysisStatusFilter = 'all';

const MARKET_LABEL = { a: 'A 股', us: '美股' };
const MARKET_CURRENCY = { a: 'CNY', us: 'USD' };
const DEFAULT_STOP_LOSS_RATIO = -0.08;
const DEFAULT_TAKE_PROFIT_RATIO = 0.20;

function classifyAlphaMarket(symbol) {
  return String(symbol || '').trim().toUpperCase().endsWith('.US') ? 'us' : 'a';
}

function alphaActionClass(action) {
  const normalized = String(action || 'HOLD').toLowerCase();
  if (normalized === 'buy') return 'buy';
  if (normalized === 'sell') return 'sell';
  return 'hold';
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
    saveButton.textContent = '保存';
  }
  alphaEditingSymbol = null;
  alphaEditingEntryIds = [];
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
    saveButton.textContent = '保存编辑';
  }
  focusAlphaBuilder();
}

function beginAlphaSymbolEdit(symbol, entries) {
  const normalizedSymbol = String(symbol || '').toUpperCase();
  alphaEditingHoldingId = null;
  alphaEditingSymbol = normalizedSymbol;
  alphaEditingEntryIds = entries.map((entry) => entry.entry_id).filter(Boolean);
  const lots = entries.map((entry) => ({
    buy_date: entry.buy_date,
    buy_price: entry.buy_price,
    quantity: entry.quantity,
  }));
  const root = document.getElementById('alpha-stock-cards');
  if (!root) return;
  root.innerHTML = createAlphaStockCard({ symbol: normalizedSymbol, lots });
  const saveButton = document.getElementById('alpha-analysis-save');
  if (saveButton) {
    delete saveButton.dataset.alphaEditEntryId;
    saveButton.textContent = '保存编辑';
  }
  focusAlphaBuilder();
  showToast(`正在编辑 ${normalizedSymbol} 的 ${entries.length} 个批次`, 'info', { position: 'bottom-right', duration: 2500 });
}

function focusAlphaBuilder() {
  const builder = document.getElementById('alpha-analysis-builder');
  const symbolInput = builder?.querySelector('[data-alpha-symbol]');
  builder?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  setTimeout(() => symbolInput?.focus(), 250);
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

function aggregateAlphaHoldingsBySymbol(entries) {
  const groups = {};
  entries.forEach((entry) => {
    const symbol = String(entry.symbol || '').trim().toUpperCase();
    if (!symbol) return;
    const market = classifyAlphaMarket(symbol);
    const bucket = groups[symbol] || (groups[symbol] = {
      symbol,
      market,
      currency: MARKET_CURRENCY[market],
      entries: [],
      total_quantity: 0,
      total_cost: 0,
      weighted_avg_cost: 0,
      lot_count: 0,
      first_buy_date: null,
      last_buy_date: null,
      stop_loss_ratio: DEFAULT_STOP_LOSS_RATIO,
      take_profit_ratio: DEFAULT_TAKE_PROFIT_RATIO,
    });
    bucket.entries.push(entry);
    const quantity = Number(entry.quantity || 0);
    const buyPrice = Number(entry.buy_price || 0);
    bucket.total_quantity += quantity;
    bucket.total_cost += quantity * buyPrice;
    bucket.lot_count += 1;
    if (!bucket.first_buy_date || entry.buy_date < bucket.first_buy_date) {
      bucket.first_buy_date = entry.buy_date;
    }
    if (!bucket.last_buy_date || entry.buy_date > bucket.last_buy_date) {
      bucket.last_buy_date = entry.buy_date;
    }
    if (entry.stop_loss_ratio !== null && entry.stop_loss_ratio !== undefined) {
      bucket.stop_loss_ratio = Number(entry.stop_loss_ratio);
    }
    if (entry.take_profit_ratio !== null && entry.take_profit_ratio !== undefined) {
      bucket.take_profit_ratio = Number(entry.take_profit_ratio);
    }
  });
  Object.values(groups).forEach((bucket) => {
    bucket.weighted_avg_cost = bucket.total_quantity > 0
      ? bucket.total_cost / bucket.total_quantity
      : 0;
  });
  return groups;
}

function buildAlphaPositionCard(symbol, aggregate, position) {
  const latestPrice = Number(position?.mark_price ?? position?.latest_price ?? aggregate.weighted_avg_cost);
  const totalQuantity = aggregate.total_quantity;
  const avgCost = aggregate.weighted_avg_cost;
  const marketValue = Number.isFinite(latestPrice) ? latestPrice * totalQuantity : 0;
  const unrealizedPnl = Number.isFinite(latestPrice) ? (latestPrice - avgCost) * totalQuantity : 0;
  const unrealizedPnlRatio = avgCost > 0 && Number.isFinite(latestPrice)
    ? (latestPrice - avgCost) / avgCost
    : 0;
  const stopLossRatio = Number(aggregate.stop_loss_ratio ?? DEFAULT_STOP_LOSS_RATIO);
  const takeProfitRatio = Number(aggregate.take_profit_ratio ?? DEFAULT_TAKE_PROFIT_RATIO);

  let alertLevel = 'ok';
  if (unrealizedPnlRatio <= stopLossRatio) alertLevel = 'stop_loss';
  else if (unrealizedPnlRatio >= takeProfitRatio) alertLevel = 'take_profit';

  const distanceStopLoss = unrealizedPnlRatio - stopLossRatio;
  const distanceTakeProfit = takeProfitRatio - unrealizedPnlRatio;
  const pnlTone = unrealizedPnl >= 0 ? 'positive' : 'negative';

  return `
    <article class="alpha-position-card alert-${escapeHtml(alertLevel)}" data-alpha-symbol="${escapeHtml(symbol)}">
      <div class="alpha-position-card-head">
        <span class="alpha-position-card-symbol">${escapeHtml(symbol)} · ${escapeHtml(aggregate.currency)}</span>
        <div class="alpha-position-card-actions">
          <button type="button" class="alpha-holding-analyze" data-alpha-holding-analyze="${escapeHtml(symbol)}">分析</button>
          <button type="button" class="alpha-builder-add-lot" data-alpha-history-edit data-alpha-edit-entry-symbol="${escapeHtml(symbol)}">编辑</button>
          <button type="button" class="alpha-builder-remove" data-alpha-history-delete data-alpha-delete-entry-symbol="${escapeHtml(symbol)}">删除</button>
        </div>
      </div>
      <div class="alpha-position-card-grid">
        <div>
          <div class="alpha-position-card-label">现价</div>
          <div class="alpha-position-card-value">${escapeHtml(formatNumber(latestPrice, 4))} ${escapeHtml(aggregate.currency)}</div>
        </div>
        <div>
          <div class="alpha-position-card-label">持仓成本</div>
          <div class="alpha-position-card-value">${escapeHtml(formatNumber(avgCost, 4))} ${escapeHtml(aggregate.currency)}（均价）</div>
        </div>
        <div>
          <div class="alpha-position-card-label">持仓数量</div>
          <div class="alpha-position-card-value">${escapeHtml(formatNumber(totalQuantity, 4))} 股</div>
        </div>
        <div>
          <div class="alpha-position-card-label">市值</div>
          <div class="alpha-position-card-value">${escapeHtml(formatNumber(marketValue, 2))} ${escapeHtml(aggregate.currency)}</div>
        </div>
        <div>
          <div class="alpha-position-card-label">首次买入</div>
          <div class="alpha-position-card-value">${escapeHtml(aggregate.first_buy_date || '--')}</div>
        </div>
        <div>
          <div class="alpha-position-card-label">最近买入</div>
          <div class="alpha-position-card-value">${escapeHtml(aggregate.last_buy_date || '--')}</div>
        </div>
      </div>
      <div class="alpha-position-card-pnl">
        <span class="alpha-position-card-label">浮盈金额</span>
        <span class="alpha-position-card-pnl-amount ${pnlTone}">${escapeHtml(formatSignedCurrency(unrealizedPnl, aggregate.currency))}</span>
        <span class="alpha-position-card-label">浮盈比例</span>
        <span class="alpha-position-card-pnl-ratio ${pnlTone}">${escapeHtml(formatSignedPercent(unrealizedPnlRatio * 100))}</span>
      </div>
      <div class="alpha-position-card-thresholds">
        <span class="alpha-position-card-label">距止损 ${escapeHtml(formatSignedPercent(distanceStopLoss * 100))}</span>
        <span class="alpha-position-card-label">距止盈 ${escapeHtml(formatSignedPercent(distanceTakeProfit * 100))}</span>
        <span class="alpha-position-card-threshold-tag ${alertLevel === 'stop_loss' ? 'current-stop-loss' : 'stop-loss'}">止损 ${escapeHtml(formatPercent(stopLossRatio))}</span>
        <span class="alpha-position-card-threshold-tag ${alertLevel === 'take_profit' ? 'current-take-profit' : 'take-profit'}">止盈 +${escapeHtml(formatPercent(takeProfitRatio).replace('-', ''))}</span>
        <span class="alpha-position-card-threshold-tag">批次 ${escapeHtml(String(aggregate.lot_count))}</span>
      </div>
    </article>
  `;
}

function formatSignedCurrency(raw, currency) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  const sign = n > 0 ? '+' : '';
  return `${sign}${currency} ${n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function renderAlphaHoldingsSummary(summaryList) {
  const root = document.getElementById('alpha-holdings-summary');
  if (!root) return;
  const bucket = summaryList.find((item) => item.market === currentMarket) || {
    market: currentMarket,
    currency: MARKET_CURRENCY[currentMarket],
    holdings_count: 0,
    lots_count: 0,
    total_cost: 0,
    market_value: 0,
    unrealized_pnl: 0,
    unrealized_pnl_ratio: 0,
  };
  const cards = [
    {
      label: '持仓成本',
      value: formatCurrencyRaw(Number(bucket.total_cost || 0), bucket.currency),
      tone: 'neutral',
    },
    {
      label: '当前市值',
      value: formatCurrencyRaw(Number(bucket.market_value || 0), bucket.currency),
      tone: 'neutral',
    },
    {
      label: '未实现盈亏',
      value: formatSignedCurrency(Number(bucket.unrealized_pnl || 0), bucket.currency),
      tone: Number(bucket.unrealized_pnl || 0) >= 0 ? 'positive' : 'negative',
    },
    {
      label: '持仓 / 批次',
      value: `${bucket.holdings_count || 0} / ${bucket.lots_count || 0}`,
      tone: 'neutral',
    },
  ];
  root.innerHTML = cards.map((card) => `
    <div class="alpha-summary-card">
      <div class="alpha-summary-label">${escapeHtml(card.label)} <span class="alpha-summary-currency">${escapeHtml(bucket.currency)}</span></div>
      <div class="alpha-summary-value ${card.tone}">${escapeHtml(card.value)}</div>
    </div>
  `).join('');
}

function formatCurrencyRaw(raw, currency) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  return `${currency} ${n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function renderAlphaPositions(positions) {
  const root = document.getElementById('alpha-positions');
  if (!root) return;
  const aggregates = aggregateAlphaHoldingsBySymbol(alphaHoldingsEntriesCache);
  const filtered = Object.values(aggregates).filter((agg) => agg.market === currentMarket);
  if (!filtered.length) {
    root.innerHTML = `<div class="alpha-empty-state">暂无 ${escapeHtml(MARKET_LABEL[currentMarket])} 持仓，先在下方录入买入批次。</div>`;
    return;
  }
  root.innerHTML = filtered
    .sort((a, b) => a.symbol.localeCompare(b.symbol))
    .map((agg) => {
      const position = positions.find((p) => String(p.symbol || '').toUpperCase() === agg.symbol) || agg;
      return buildAlphaPositionCard(agg.symbol, agg, position);
    })
    .join('');
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
  alphaPositionsBySymbol = positions.reduce((acc, pos) => {
    acc[String(pos.symbol || '').toUpperCase()] = pos;
    return acc;
  }, {});
  renderAlphaFillHistory(fills.filter((fill) => {
    const symbol = String(fill.asset_symbol || fill.symbol || '').toUpperCase();
    return symbol && (classifyAlphaMarket(symbol) === currentMarket);
  }));
  renderAlphaMultiLegHistory(fills.filter((fill) => {
    const symbol = String(fill.asset_symbol || fill.symbol || '').toUpperCase();
    return symbol && (classifyAlphaMarket(symbol) === currentMarket);
  }));
  renderAlphaPositions(positions);
  if (snapshot && !alphaHoldingsSummaryCache.summary?.length) {
    renderAlphaHoldingsSummary([
      {
        market: currentMarket,
        currency: MARKET_CURRENCY[currentMarket],
        holdings_count: positions.length,
        lots_count: fills.length,
        total_cost: snapshot.cash_balance || 0,
        market_value: snapshot.nav || 0,
        unrealized_pnl: snapshot.unrealized_pnl || 0,
        unrealized_pnl_ratio: 0,
      },
    ]);
  } else {
    renderAlphaHoldingsSummary(alphaHoldingsSummaryCache.summary || []);
  }
}

function renderAlphaSavedHoldings(items) {
  const root = document.getElementById('alpha-holdings-records');
  if (!root) return;
  const filtered = items.filter((item) => classifyAlphaMarket(item.symbol) === currentMarket);
  if (!filtered.length) {
    root.innerHTML = '<div class="alpha-empty-state">暂无已保存买入记录</div>';
    return;
  }
  root.innerHTML = filtered.map((item) => `
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

function updateAlphaMarketHeader() {
  const label = document.getElementById('alpha-current-market-label');
  const currency = document.getElementById('alpha-current-currency-label');
  if (label) label.textContent = MARKET_LABEL[currentMarket] || currentMarket;
  if (currency) currency.textContent = MARKET_CURRENCY[currentMarket] || '--';
}

function setAlphaActiveMarketTab() {
  document.querySelectorAll('[data-alpha-market]').forEach((tab) => {
    const isActive = tab.dataset.alphaMarket === currentMarket;
    tab.classList.toggle('active', isActive);
    tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });
  updateAlphaMarketHeader();
}

async function loadAlphaWorkbench() {
  const res = await fetch(WORKBENCH_API);
  if (!res.ok) {
    throw new Error('alpha workbench load failed');
  }
  const data = await res.json();
  renderAlphaPortfolio(data.alpha?.portfolio || {});
}

async function loadAlphaSavedHoldings(market = currentMarket) {
  const res = await fetch(ALPHA_HOLDINGS_API);
  if (!res.ok) {
    throw new Error('alpha holdings load failed');
  }
  const data = await res.json();
  const allItems = toList(data.items);
  alphaHoldingsEntriesCache = allItems;
  renderAlphaSavedHoldings(allItems);
  return allItems.filter((item) => classifyAlphaMarket(item.symbol) === market);
}

async function loadAlphaSummary(market = currentMarket) {
  try {
    const res = await fetch(ALPHA_HOLDINGS_SUMMARY_API);
    if (!res.ok) {
      throw new Error(`summary failed (${res.status})`);
    }
    const data = await res.json();
    alphaHoldingsSummaryCache = data || { summary: [] };
  } catch (error) {
    console.warn('alpha summary load failed, falling back to snapshot', error);
    alphaHoldingsSummaryCache = { summary: [] };
  }
  renderAlphaHoldingsSummary(alphaHoldingsSummaryCache.summary || []);
}

async function loadAlphaHoldings(market = currentMarket) {
  await loadAlphaSavedHoldings(market);
  await loadAlphaSummary(market);
  await loadAlphaWorkbench();
}

async function startAlphaAnalysis(symbol) {
  const res = await fetch(ALPHA_ANALYSIS_RUNS_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ symbol, backtest_window: '60d', include_backtest: true }),
  });
  const data = await parseResponseBody(res);
  if (res.status === 409) {
    const activeId = data?.detail?.active_run_id || '';
    addAlert('warn', `已有活跃分析运行: ${activeId}`);
    return null;
  }
  if (!res.ok) {
    throw new Error(extractErrorMessage(data, `分析启动失败 (${res.status})`));
  }
  subscribeAlphaAnalysisEvents(data.run_id, symbol);
  upsertAnalysisRow({ ...data, stage: data.status || 'accepted', status: data.status || 'accepted' });
  return data;
}

function subscribeAlphaAnalysisEvents(runId, symbol) {
  if (typeof EventSource === 'undefined') return;
  const es = new EventSource(`/api/v1/alpha/analysis-runs/${runId}/events`);
  es.addEventListener('accepted', () => {
    upsertAnalysisRow({ run_id: runId, symbol, stage: 'accepted', status: 'done' });
  });
  es.addEventListener('snapshot', (ev) => {
    const payload = JSON.parse(ev.data || '{}');
    upsertAnalysisRow({ ...payload, run_id: runId, symbol, stage: 'snapshot' });
  });
  es.addEventListener('research', (ev) => {
    const payload = JSON.parse(ev.data || '{}');
    upsertAnalysisRow({ ...payload, run_id: runId, symbol, stage: 'research' });
  });
  es.addEventListener('trader', (ev) => {
    const payload = JSON.parse(ev.data || '{}');
    upsertAnalysisRow({ ...payload, run_id: runId, symbol, stage: 'trader' });
  });
  es.addEventListener('risk', (ev) => {
    const payload = JSON.parse(ev.data || '{}');
    upsertAnalysisRow({ ...payload, run_id: runId, symbol, stage: 'risk' });
  });
  es.addEventListener('backtest', (ev) => {
    const payload = JSON.parse(ev.data || '{}');
    upsertAnalysisRow({ ...payload, run_id: runId, symbol, stage: 'backtest' });
  });
  es.addEventListener('completed', (ev) => {
    const payload = JSON.parse(ev.data || '{}');
    upsertAnalysisRow({ ...payload, run_id: runId, symbol, stage: 'completed' });
    es.close();
  });
  es.addEventListener('failed', (ev) => {
    const payload = JSON.parse(ev.data || '{}');
    upsertAnalysisRow({ ...payload, run_id: runId, symbol, stage: 'failed' });
    es.close();
  });
  es.onerror = () => {
    // 如果 run 已处于终态，直接关闭，不重连
    const row = document.querySelector(`[data-run-id="${runId}"]`);
    const stage = row?.querySelector('.alpha-analysis-stage')?.textContent || '';
    if (stage.includes('完成') || stage.includes('失败') || stage === 'completed' || stage === 'failed') {
      es.close();
    }
  };
}

function upsertAnalysisRow(data) {
  const list = document.getElementById('alpha-analysis-list');
  if (!list) return;
  const empty = list.querySelector('.alpha-empty-state');
  if (empty) empty.remove();
  let row = list.querySelector(`[data-run-id="${data.run_id}"]`);
  if (!row) {
    row = document.createElement('div');
    row.className = 'alpha-analysis-row';
    row.setAttribute('data-run-id', data.run_id);
    row.setAttribute('data-symbol', data.symbol);
    row.innerHTML = `
      <span class="alpha-analysis-symbol"></span>
      <span class="alpha-analysis-stage"></span>
      <span class="alpha-analysis-status"></span>
      <span class="alpha-analysis-action"></span>
      <span class="alpha-analysis-rating"></span>
	    `;
    list.prepend(row);
  }
  row.dataset.analysisPayload = JSON.stringify(data);
  row.dataset.createdAt = data.created_at || '';
  row.dataset.runId = data.run_id || '';
  row.querySelector('.alpha-analysis-symbol').textContent = data.symbol || '';
  row.querySelector('.alpha-analysis-stage').textContent = alphaStageLabel(data.stage || data.current_stage || '');
  row.querySelector('.alpha-analysis-status').textContent = alphaStatusLabel(data.status || '');
  const risk = data.risk || {};
  const research = data.research || {};
  row.querySelector('.alpha-analysis-action').textContent = risk.action || data.risk_action || '--';
  row.querySelector('.alpha-analysis-rating').textContent = research.rating || data.research_rating || '--';
  row.classList.toggle('is-failed', data.stage === 'failed' || data.status === 'failed');
  row.classList.toggle('is-completed', data.stage === 'completed' || data.status === 'completed');
  sortAlphaAnalysisRows(list);
  if (data.stage === 'failed' && row.dataset.alertedFailed !== '1') {
    row.dataset.alertedFailed = '1';
    addAlert('err', `${data.symbol} 分析失败: ${data.error || '未知错误'}`);
  }
}

function sortAlphaAnalysisRows(list) {
  const rows = Array.from(list.querySelectorAll('.alpha-analysis-row'));
  rows.sort((left, right) => {
    const leftCreated = left.dataset.createdAt || '';
    const rightCreated = right.dataset.createdAt || '';
    if (leftCreated !== rightCreated) {
      return rightCreated.localeCompare(leftCreated);
    }
    return (right.dataset.runId || '').localeCompare(left.dataset.runId || '');
  });
  rows.forEach((row) => list.appendChild(row));
}

function alphaStageLabel(stage) {
  const labels = {
    accepted: '已接收',
    running: '运行中',
    snapshot: '快照',
    research: '研究',
    trader: '交易员',
    risk: '风控',
    backtest: '回测',
    completed: '完成',
    failed: '失败',
  };
  return labels[stage] || stage || '--';
}

function alphaStatusLabel(status) {
  const labels = {
    accepted: '排队中',
    running: '分析中',
    started: '进行中',
    done: '完成',
    completed: '完成',
    failed: '失败',
  };
  return labels[status] || status || '--';
}

function alphaRunSummaryPayload(run) {
  return {
    run_id: run.run_id,
    symbol: run.symbol,
    market: run.market,
    stage: run.current_stage,
    status: run.status,
    risk_action: run.risk_action,
    research_rating: run.research_rating,
    research_confidence: run.research_confidence,
    close_date: run.close_date,
    created_at: run.created_at,
    finished_at: run.finished_at,
  };
}

async function loadAlphaAnalysisRuns({ append = false } = {}) {
  const params = new URLSearchParams({ market: currentMarket, limit: '20' });
  if (alphaAnalysisStatusFilter !== 'all') params.set('status', alphaAnalysisStatusFilter);
  if (append && alphaAnalysisRunsCursor) params.set('cursor', alphaAnalysisRunsCursor);
  const res = await fetch(`${ALPHA_ANALYSIS_RUNS_API}?${params.toString()}`);
  if (!res.ok) throw new Error(`分析历史加载失败 (${res.status})`);
  const data = await res.json();
  const list = document.getElementById('alpha-analysis-list');
  if (!list) return;
  if (!append) list.innerHTML = '';
  const runs = toList(data.items);
  runs.forEach((run) => upsertAnalysisRow(alphaRunSummaryPayload(run)));
  alphaAnalysisRunsCursor = data.next_cursor || null;
  if (!runs.length && !append) {
    list.innerHTML = '<div class="alpha-empty-state">暂无分析记录，从持仓卡点击「分析」开始。</div>';
  }
  const status = document.getElementById('alpha-analysis-pagination-status');
  if (status) status.textContent = `已加载 ${list.querySelectorAll('.alpha-analysis-row').length} 条`;
  const loadMore = document.getElementById('alpha-analysis-load-more');
  if (loadMore) loadMore.hidden = !alphaAnalysisRunsCursor;
}

const ALPHA_FIELD_LABELS = {
  // overview / snapshot
  currency: '币种', as_of: '数据时间', close: '收盘价',
  weighted_avg_cost: '持仓均价', quantity: '持仓数量',
  unrealized_pnl: '浮动盈亏', unrealized_pnl_ratio: '浮动盈亏比例',
  market_value: '市值', position_ratio: '仓位比例',
  stop_loss_ratio: '止损比例', take_profit_ratio: '止盈比例',
  error: '错误信息',
  // research
  rating: '评级', thesis: '核心论点',
  technical_view: '技术面观点', fundamental_view: '基本面观点',
  sentiment_view: '情绪面观点', catalysts: '催化剂',
  risks: '风险因素', confidence: '置信度',
  data_gaps: '数据缺口',
  // trader
  action: '操作建议', reasoning: '理由',
  entry_low: '入场价下限', entry_high: '入场价上限',
  stop_loss: '止损价', take_profit: '止盈价',
  // risk
  triggered_rules: '触发规则', approved_position_ratio: '批准仓位比例',
  reason: '原因',
};

function alphaFieldLabel(key) {
  return ALPHA_FIELD_LABELS[key] || key.replace(/_/g, ' ');
}

function alphaRatingBadge(rating) {
  const map = {
    BUY: ['买入', 'badge-buy'], OVERWEIGHT: ['超配', 'badge-overweight'],
    HOLD: ['持有', 'badge-hold'], UNDERWEIGHT: ['低配', 'badge-underweight'],
    SELL: ['卖出', 'badge-sell'],
    ADD: ['加仓', 'badge-buy'], REDUCE: ['减仓', 'badge-sell'],
    EXIT: ['清仓', 'badge-sell'],
  };
  const [label, cls] = map[rating] || [rating, 'badge-hold'];
  return `<span class="alpha-badge ${cls}">${escapeHtml(label)}</span>`;
}

function renderAnalysisObject(value, section) {
  if (!value) return '<div class="alpha-empty-state">暂无数据</div>';
  if (typeof value !== 'object') return `<p>${escapeHtml(String(value))}</p>`;
  const rows = Object.entries(value).map(([key, raw]) => {
    const label = alphaFieldLabel(key);
    let rendered;
    if (Array.isArray(raw)) {
      rendered = raw.map((item) => `<span class="alpha-tag">${escapeHtml(String(item))}</span>`).join('');
      return `<div class="alpha-detail-row"><span class="alpha-detail-key">${escapeHtml(label)}</span><div class="alpha-detail-val alpha-tag-list">${rendered}</div></div>`;
    }
    if ((key === 'rating' || key === 'action') && typeof raw === 'string') {
      rendered = alphaRatingBadge(raw);
    } else if (key === 'confidence' || key === 'position_ratio' || key === 'approved_position_ratio' || key === 'unrealized_pnl_ratio' || key === 'stop_loss_ratio' || key === 'take_profit_ratio') {
      rendered = `<span class="alpha-num">${escapeHtml((Number(raw) * 100).toFixed(1))}%</span>`;
    } else {
      rendered = escapeHtml(normalizeText(raw, '--'));
    }
    return `<div class="alpha-detail-row"><span class="alpha-detail-key">${escapeHtml(label)}</span><div class="alpha-detail-val">${rendered}</div></div>`;
  }).join('');
  return `<div class="alpha-detail-grid">${rows}</div>`;
}

function setDrawerSection(section, html) {
  const root = document.querySelector(`#alpha-analysis-drawer [data-section="${section}"] .alpha-analysis-drawer-content`);
  if (root) root.innerHTML = html;
}

async function openAlphaAnalysisDrawer(runId) {
  const res = await fetch(`${ALPHA_ANALYSIS_RUNS_API}/${encodeURIComponent(runId)}`);
  const detail = await parseResponseBody(res);
  if (!res.ok) {
    throw new Error(extractErrorMessage(detail, `分析详情加载失败 (${res.status})`));
  }
  const drawer = document.getElementById('alpha-analysis-drawer');
  if (!drawer) return;
  document.getElementById('alpha-analysis-drawer-symbol').textContent = detail.symbol || '--';
  document.getElementById('alpha-analysis-drawer-status').textContent = `${alphaStatusLabel(detail.status)} · ${alphaStageLabel(detail.current_stage)} · ${normalizeText(detail.finished_at || detail.created_at, '--')}`;
  const snapshot = detail.snapshot || {};
  setDrawerSection('overview', renderAnalysisObject({
    currency: snapshot.currency,
    as_of: snapshot.as_of,
    close: snapshot.close,
    weighted_avg_cost: snapshot.weighted_avg_cost,
    quantity: snapshot.quantity,
    unrealized_pnl: snapshot.unrealized_pnl,
    unrealized_pnl_ratio: snapshot.unrealized_pnl_ratio,
    error: detail.error,
  }));
  setDrawerSection('research', renderAnalysisObject(detail.research));
  setDrawerSection('trader', renderAnalysisObject(detail.trader));
  setDrawerSection('risk', renderAnalysisObject(detail.risk));
  setDrawerSection('backtest', renderAnalysisObject(detail.backtest));
  setDrawerSection('events', `<div class="alpha-event-list">${toList(detail.events).map((event) => `
    <div class="alpha-event-row">
      <span>${escapeHtml(String(event.seq))}</span>
      <strong>${escapeHtml(alphaStageLabel(event.stage))}</strong>
      <span>${escapeHtml(alphaStatusLabel(event.status))}</span>
      <span>${escapeHtml(normalizeText(event.created_at, '--'))}</span>
    </div>`).join('')}</div>`);
  drawer.hidden = false;
  drawer.setAttribute('aria-hidden', 'false');
}

function closeAlphaAnalysisDrawer() {
  const drawer = document.getElementById('alpha-analysis-drawer');
  if (!drawer) return;
  drawer.hidden = true;
  drawer.setAttribute('aria-hidden', 'true');
}

document.getElementById('alpha-positions')?.addEventListener('click', (event) => {
  const btn = event.target.closest('[data-alpha-holding-analyze]');
  if (!btn) return;
  event.preventDefault();
  const symbol = btn.getAttribute('data-alpha-holding-analyze');
  if (!symbol) return;
  btn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = '分析中…';
  startAlphaAnalysis(symbol).then((result) => {
    if (result) {
      btn.textContent = '已启动';
      setTimeout(() => { btn.textContent = originalText; btn.disabled = false; }, 3000);
    } else {
      btn.textContent = originalText;
      btn.disabled = false;
    }
  }).catch((error) => {
    addAlert('err', `分析启动失败: ${error.message}`);
    btn.textContent = originalText;
    btn.disabled = false;
  });
});
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

document.getElementById('alpha-market-tabs')?.addEventListener('click', async (event) => {
  const tab = event.target.closest('[data-alpha-market]');
  if (!tab) return;
  const nextMarket = tab.dataset.alphaMarket;
  if (!nextMarket || nextMarket === currentMarket) return;
  currentMarket = nextMarket;
  setAlphaActiveMarketTab();
  try {
    await loadAlphaHoldings(currentMarket);
    alphaAnalysisRunsCursor = null;
    await loadAlphaAnalysisRuns();
  } catch (error) {
    console.error('切换市场失败:', error);
    showToast(`切换到 ${MARKET_LABEL[currentMarket]} 失败: ${error.message}`, 'error', { position: 'bottom-right', duration: 3000 });
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
  alphaEditingSymbol = null;
  alphaEditingEntryIds = [];
  resetAlphaBuilder();
  await loadAlphaHoldings(currentMarket);
  return data;
}

async function saveAlphaHoldings(options = {}) {
  const { silent = false } = options;
  const btn = document.getElementById('alpha-analysis-save');
  const editingEntryId = btn?.dataset?.alphaEditEntryId || alphaEditingHoldingId;
  if (btn && !silent) {
    btn.disabled = true;
    btn.textContent = '保存中...';
  }

  const entries = collectAlphaHoldingEntries();

  try {
    if (!entries.length) {
      throw new Error('请至少填写一条有效的买入记录');
    }
    if (alphaEditingSymbol) {
      const symbols = Array.from(new Set(entries.map((entry) => entry.symbol)));
      if (symbols.length !== 1 || symbols[0] !== alphaEditingSymbol) {
        throw new Error(`编辑 ${alphaEditingSymbol} 时不能改成其他股票`);
      }
      for (const entryId of alphaEditingEntryIds) {
        const res = await fetch(`${ALPHA_HOLDINGS_API}/${encodeURIComponent(entryId)}`, { method: 'DELETE' });
        const data = await parseResponseBody(res);
        if (!res.ok) {
          throw new Error(extractErrorMessage(data, `删除旧批次失败 (${res.status})`));
        }
      }
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
    } else if (editingEntryId) {
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
    alphaEditingSymbol = null;
    alphaEditingEntryIds = [];
    resetAlphaBuilder();
    await loadAlphaHoldings(currentMarket);
    if (btn && !silent) {
      btn.textContent = '已保存';
      setTimeout(() => { btn.textContent = '保存'; btn.disabled = false; }, 2000);
    }

    const symbolsAdded = Array.from(new Set(entries.map((entry) => entry.symbol)));
    const totalHoldings = alphaHoldingsEntriesCache.length;
    const symbolSummary = symbolsAdded.length === 1
      ? `${symbolsAdded[0]} ${entries.length} 笔`
      : `${symbolsAdded.join('/')} 共 ${entries.length} 笔`;
    showToast(`已添加 ${symbolSummary}，当前持仓 ${totalHoldings} 股`, 'success', { position: 'bottom-right', duration: 3000 });
    return { entries, totalHoldings };
  } catch (error) {
    if (btn && !silent) {
      btn.textContent = '保存失败';
      btn.disabled = false;
      setTimeout(() => { btn.textContent = '保存'; }, 2000);
    }
    showToast('保存失败: ' + error.message, 'error', { position: 'bottom-right', duration: 3000 });
    throw error;
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
    const confirmed = window.confirm(`删除 ${entry?.buy_date || ''} 这笔？会重新计算均价`);
    if (!confirmed) return;
    await deleteAlphaHolding(entryId);
  }
});

document.getElementById('alpha-positions')?.addEventListener('click', async (event) => {
  const trigger = event.target.closest('button');
  if (!trigger) return;
  const symbol = trigger.getAttribute('data-alpha-edit-entry-symbol') || trigger.getAttribute('data-alpha-delete-entry-symbol');
  if (!symbol) return;
  const entries = alphaHoldingsEntriesCache.filter((item) => String(item.symbol || '').toUpperCase() === symbol);
  if (!entries.length) return;
  if (trigger.matches('[data-alpha-history-edit]')) {
    beginAlphaSymbolEdit(symbol, entries);
    return;
  }
  if (trigger.matches('[data-alpha-history-delete]')) {
    const confirmed = window.confirm(`删除 ${symbol} 所有 ${entries.length} 笔？会重新计算均价`);
    if (!confirmed) return;
    try {
      for (const entry of entries) {
        await deleteAlphaHolding(entry.entry_id);
      }
      showToast(`已删除 ${symbol} ${entries.length} 笔`, 'success', { position: 'bottom-right', duration: 3000 });
    } catch (error) {
      showToast('删除失败: ' + error.message, 'error', { position: 'bottom-right', duration: 3000 });
    }
  }
});

document.getElementById('alpha-analysis-save')?.addEventListener('click', () => {
  saveAlphaHoldings().catch(() => {});
});
document.getElementById('alpha-analysis-list')?.addEventListener('click', (event) => {
  const row = event.target.closest('[data-run-id]');
  if (!row) return;
  openAlphaAnalysisDrawer(row.getAttribute('data-run-id')).catch((error) => {
    showToast(error.message, 'error', { position: 'bottom-right', duration: 3000 });
  });
});
document.getElementById('alpha-analysis-drawer-close')?.addEventListener('click', closeAlphaAnalysisDrawer);
document.getElementById('alpha-analysis-filters')?.addEventListener('click', (event) => {
  const filter = event.target.closest('[data-alpha-status-filter]');
  if (!filter) return;
  alphaAnalysisStatusFilter = filter.dataset.alphaStatusFilter || 'all';
  document.querySelectorAll('[data-alpha-status-filter]').forEach((button) => {
    button.classList.toggle('active', button === filter);
  });
  alphaAnalysisRunsCursor = null;
  loadAlphaAnalysisRuns().catch((error) => showToast(error.message, 'error', { position: 'bottom-right', duration: 3000 }));
});
document.getElementById('alpha-analysis-load-more')?.addEventListener('click', () => {
  loadAlphaAnalysisRuns({ append: true }).catch((error) => showToast(error.message, 'error', { position: 'bottom-right', duration: 3000 }));
});
setAlphaActiveMarketTab();
ensureAlphaAnalysisBuilder();
loadAlphaHoldings(currentMarket).then(() => loadAlphaAnalysisRuns()).catch((error) => console.error('加载持仓失败:', error));
