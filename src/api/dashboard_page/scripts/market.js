// 行情相关 API 常量
const MARKET_QUOTE_API = '/api/v1/market/quote';
const MARKET_BULK_API = '/api/v1/market/bulk';

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
    const close = Number(item.close);
    const changePct = Number(item.change_pct);
    const cls = (changePct ?? 0) > 0 ? 'quote-up' : (changePct ?? 0) < 0 ? 'quote-down' : '';
    const rowCls = (changePct ?? 0) > 0 ? 'row-up' : (changePct ?? 0) < 0 ? 'row-down' : '';
    const changeAmt = Number(item.prev_close) ? (close - Number(item.prev_close)).toFixed(2) : '--';
    return `<tr class="${rowCls}">
      <td style="color:var(--dim);font-size:11px">${escapeHtml(now)}</td>
      <td>${escapeHtml(symbol)} ${escapeHtml(name)}</td>
      <td class="${cls}">${escapeHtml(formatNumber(close))}</td>
      <td class="${cls}">${escapeHtml(String(changeAmt))}</td>
      <td class="${cls}">${escapeHtml(formatSignedPercent(changePct))}</td>
      <td>${escapeHtml(formatNumber(item.open))}</td>
      <td>${escapeHtml(formatNumber(item.high))}</td>
      <td>${escapeHtml(formatNumber(item.low))}</td>
      <td>${escapeHtml(formatVolume(item.volume))}</td>
      <td>${escapeHtml(formatNumber(item.turnover))}%</td>
      <td>${escapeHtml(formatNumber(item.amplitude))}%</td>
      <td>${escapeHtml(formatNumber(item.volume_ratio))}</td>
    </tr>`;
  }).join('');
}

async function refreshMarketQuotes() {
  const symbols = buildQuoteSymbols();
  if (!symbols.length) {
    renderMarketQuotes([]);
    return;
  }
  try {
    const res = await fetch(MARKET_BULK_API, {
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

async function searchStock() {
  const input = document.getElementById('stock-search-input');
  const statusEl = document.getElementById('search-status');
  const marketSelect = document.getElementById('market-select');
  const query = input.value.trim();
  const market = marketSelect.value;

  if (!query) {
    statusEl.textContent = '请输入股票代码或名称';
    statusEl.style.color = 'var(--yellow)';
    return;
  }

  statusEl.textContent = '搜索中...';
  statusEl.style.color = 'var(--yellow)';

  try {
    let url;
    if (market === 'us') {
      url = `/api/v1/market/stocks/us?query=${encodeURIComponent(query)}&limit=20`;
    } else {
      url = `/api/v1/market/stocks?query=${encodeURIComponent(query)}&limit=20`;
    }

    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`搜索失败 (${res.status})`);
    }

    searchResults = await res.json();
    selectedSearchIndex = -1;

    if (searchResults.length === 0) {
      statusEl.textContent = '未找到匹配的股票';
      statusEl.style.color = 'var(--yellow)';
      return;
    }

    statusEl.textContent = `找到 ${searchResults.length} 个结果`;
    statusEl.style.color = 'var(--green)';
    isSearchMode = true;

    if (market === 'us') {
      renderUsSearchQuotes(searchResults);
    } else {
      await loadSearchQuotes();
    }

  } catch (error) {
    statusEl.textContent = `搜索失败: ${error.message}`;
    statusEl.style.color = 'var(--red)';
    const tb = document.getElementById('tb-market-full');
    if (tb) {
      tb.innerHTML = '<tr><td colspan="12" class="market-empty" style="color:var(--red)">搜索失败，请重试</td></tr>';
    }
  }
}

function renderUsSearchQuotes(quotes) {
  const tb = document.getElementById('tb-market-full');
  if (!quotes || quotes.length === 0) {
    tb.innerHTML = '<tr><td colspan="12" class="market-empty">暂无行情数据</td></tr>';
    return;
  }

  const now = new Date().toLocaleTimeString('zh-CN', {hour12:false});
  tb.innerHTML = quotes.map((item, index) => {
    const symbol = normalizeText(item.symbol, '--');
    const name = normalizeText(item.name, '');
    const close = Number(item.close);
    const changePct = Number(item.change_pct);
    const cls = (changePct ?? 0) > 0 ? 'quote-up' : (changePct ?? 0) < 0 ? 'quote-down' : '';
    const rowCls = (changePct ?? 0) > 0 ? 'row-up' : (changePct ?? 0) < 0 ? 'row-down' : '';
    const changeAmt = normalizeText(item.change, '--');
    const selectedStyle = index === selectedSearchIndex ? 'background:rgba(96,165,250,.15)' : '';

    return `<tr class="${rowCls}" onclick="selectSearchResult(${index})" style="cursor:pointer;${selectedStyle}">
      <td style="color:var(--dim);font-size:11px">${escapeHtml(now)}</td>
      <td>${escapeHtml(symbol)} ${escapeHtml(name)}</td>
      <td class="${cls}">${escapeHtml(formatNumber(close))}</td>
      <td class="${cls}">${escapeHtml(String(changeAmt))}</td>
      <td class="${cls}">${escapeHtml(formatSignedPercent(changePct))}</td>
      <td>${escapeHtml(formatNumber(item.open))}</td>
      <td>${escapeHtml(formatNumber(item.high))}</td>
      <td>${escapeHtml(formatNumber(item.low))}</td>
      <td>--</td>
      <td>--</td>
      <td>--</td>
      <td>--</td>
    </tr>`;
  }).join('');
}

async function loadSearchQuotes() {
  if (searchResults.length === 0) return;

  const symbols = searchResults.map(s => s.symbol);
  const tb = document.getElementById('tb-market-full');

  try {
    const res = await fetch(MARKET_BULK_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(symbols),
    });

    if (!res.ok) {
      throw new Error('获取行情失败');
    }

    const quotes = await res.json();
    renderSearchQuotes(quotes);

  } catch (error) {
    tb.innerHTML = `<tr><td colspan="12" class="market-empty" style="color:var(--red)">获取行情失败: ${error.message}</td></tr>`;
  }
}

function renderSearchQuotes(quotes) {
  const tb = document.getElementById('tb-market-full');
  if (!quotes || quotes.length === 0) {
    tb.innerHTML = '<tr><td colspan="12" class="market-empty">暂无行情数据</td></tr>';
    return;
  }

  const now = new Date().toLocaleTimeString('zh-CN', {hour12:false});
  tb.innerHTML = quotes.map((item, index) => {
    const symbol = normalizeText(item.symbol, '--');
    const name = normalizeText(item.name, '');
    const close = Number(item.close);
    const changePct = Number(item.change_pct);
    const cls = (changePct ?? 0) > 0 ? 'quote-up' : (changePct ?? 0) < 0 ? 'quote-down' : '';
    const rowCls = (changePct ?? 0) > 0 ? 'row-up' : (changePct ?? 0) < 0 ? 'row-down' : '';
    const changeAmt = Number(item.prev_close) ? (close - Number(item.prev_close)).toFixed(2) : '--';
    const selectedStyle = index === selectedSearchIndex ? 'background:rgba(96,165,250,.15)' : '';

    return `<tr class="${rowCls}" onclick="selectSearchResult(${index})" style="cursor:pointer;${selectedStyle}">
      <td style="color:var(--dim);font-size:11px">${escapeHtml(now)}</td>
      <td>${escapeHtml(symbol)} ${escapeHtml(name)}</td>
      <td class="${cls}">${escapeHtml(formatNumber(close))}</td>
      <td class="${cls}">${escapeHtml(String(changeAmt))}</td>
      <td class="${cls}">${escapeHtml(formatSignedPercent(changePct))}</td>
      <td>${escapeHtml(formatNumber(item.open))}</td>
      <td>${escapeHtml(formatNumber(item.high))}</td>
      <td>${escapeHtml(formatNumber(item.low))}</td>
      <td>${escapeHtml(formatVolume(item.volume))}</td>
      <td>${escapeHtml(formatNumber(item.turnover))}%</td>
      <td>${escapeHtml(formatNumber(item.amplitude))}%</td>
      <td>${escapeHtml(formatNumber(item.volume_ratio))}</td>
    </tr>`;
  }).join('');
}

function selectSearchResult(index) {
  selectedSearchIndex = index;
  loadSearchQuotes();
}

function addSearchToWatchlist() {
  if (selectedSearchIndex < 0 || selectedSearchIndex >= searchResults.length) {
    document.getElementById('search-status').textContent = '请先点击选择一只股票';
    document.getElementById('search-status').style.color = 'var(--yellow)';
    return;
  }

  const stock = searchResults[selectedSearchIndex];
  const watchlistInput = document.getElementById('cfg-watchlist');
  const symbols = watchlistInput.value.split(',').map(s => s.trim()).filter(Boolean);

  if (symbols.includes(stock.symbol)) {
    document.getElementById('search-status').textContent = `${stock.symbol} 已在观察列表中`;
    document.getElementById('search-status').style.color = 'var(--yellow)';
    return;
  }

  symbols.push(stock.symbol);
  watchlistInput.value = symbols.join(',');

  document.getElementById('search-status').textContent = `已添加 ${stock.symbol} 到观察列表`;
  document.getElementById('search-status').style.color = 'var(--green)';

  savePreferences();
}

function exitSearchMode() {
  isSearchMode = false;
  searchResults = [];
  selectedSearchIndex = -1;
  document.getElementById('stock-search-input').value = '';
  document.getElementById('search-status').textContent = '';
  refreshMarketQuotes();
}
