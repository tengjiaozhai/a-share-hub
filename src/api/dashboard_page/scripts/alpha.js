// Alpha 持仓助手
const ALPHA_REPORT_API = '/api/v1/alpha/portfolio/report';
const ALPHA_HOLDINGS_API = '/api/v1/alpha/holdings';
const ALPHA_HOLDINGS_SUMMARY_API = '/api/v1/alpha/holdings/summary';
const VALID_REPORT_ACTIONS = ['HOLD', 'ADD', 'REDUCE', 'EXIT', 'WATCH'];

let alphaPortfolioSymbols = [];
let alphaEditingHoldingId = null;
let currentMarket = 'a';
let alphaHoldingsEntriesCache = [];
let alphaPositionsBySymbol = {};
let alphaHoldingsSummaryCache = { summary: [] };

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
  alphaPortfolioSymbols = positions
    .map((item) => String(item?.symbol || '').trim().toUpperCase())
    .filter(Boolean);
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
  await Promise.all([
    loadAlphaSavedHoldings(market),
    loadAlphaSummary(market),
    loadAlphaWorkbench(),
  ]);
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

document.getElementById('alpha-market-tabs')?.addEventListener('click', async (event) => {
  const tab = event.target.closest('[data-alpha-market]');
  if (!tab) return;
  const nextMarket = tab.dataset.alphaMarket;
  if (!nextMarket || nextMarket === currentMarket) return;
  currentMarket = nextMarket;
  setAlphaActiveMarketTab();
  try {
    await loadAlphaHoldings(currentMarket);
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
  resetAlphaBuilder();
  await loadAlphaHoldings(currentMarket);
  await loadAlphaReport();
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
    await loadAlphaHoldings(currentMarket);
    await loadAlphaReport();
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

document.getElementById('alpha-analysis-save-and-report')?.addEventListener('click', async () => {
  try {
    await saveAlphaHoldings();
    await loadAlphaReport();
  } catch (_) {
    // toast already shown
  }
});

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
    beginAlphaHoldingEdit(entries[0]);
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
setAlphaActiveMarketTab();
ensureAlphaAnalysisBuilder();
loadAlphaHoldings(currentMarket).catch((error) => console.error('加载持仓失败:', error));
