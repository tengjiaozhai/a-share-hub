// src/api/static/js/views/market.js

let searchMode = false;
let searchResults = [];
let selectedSearchIndex = -1;

function initMarket() {
  const searchInput = document.getElementById('stock-search-input');
  if (searchInput) {
    searchInput.addEventListener('keydown', handleSearchKeydown);
  }
  
  const marketSelect = document.getElementById('market-select');
  if (marketSelect) {
    marketSelect.addEventListener('change', handleMarketChange);
  }
}

function renderMarket() {
  refreshMarketQuotes();
}

async function refreshMarketQuotes() {
  const symbols = buildQuoteSymbols();
  if (symbols.length === 0) {
    renderMarketQuotes([]);
    return;
  }
  try {
    const data = await MarketAPI.getBulk(symbols);
    renderMarketQuotes(Array.isArray(data) ? data : []);
  } catch (err) {
    showToast('获取行情失败: ' + err.message, 'error');
    renderMarketQuotes([]);
  }
}

function buildQuoteSymbols() {
  const watchlistInput = document.getElementById('cfg-watchlist');
  if (!watchlistInput) return [];
  return watchlistInput.value
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
    
    const changeClass = item.change > 0 ? 'quote-up' : item.change < 0 ? 'quote-down' : '';
    
    return `<tr>
      <td>${escapeHtml(now)}</td>
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

function handleSearchKeydown(event) {
  if (event.key === 'Enter') {
    event.preventDefault();
    searchStock();
  }
}

function handleMarketChange(event) {
  const input = document.getElementById('stock-search-input');
  if (!input) return;
  
  if (event.target.value === 'us') {
    input.placeholder = '输入美股代码或名称（如：AAPL 或 苹果）';
  } else {
    input.placeholder = '输入股票代码或名称（如：600519 或 贵州茅台）';
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
    searchMode = true;
    
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
    const changeAmt = normalizeText(item.change, '--');
    const selectedStyle = index === selectedSearchIndex ? 'background:rgba(96,165,250,.15)' : '';
    
    return `<tr onclick="selectSearchResult(${index})" style="cursor:pointer;${selectedStyle}">
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
    const res = await fetch('/api/v1/market/bulk', {
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
    const changeAmt = Number(item.prev_close) ? (close - Number(item.prev_close)).toFixed(2) : '--';
    const selectedStyle = index === selectedSearchIndex ? 'background:rgba(96,165,250,.15)' : '';
    
    return `<tr onclick="selectSearchResult(${index})" style="cursor:pointer;${selectedStyle}">
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
  if (searchResults.length > 0) {
    const marketSelect = document.getElementById('market-select');
    if (marketSelect.value === 'us') {
      renderUsSearchQuotes(searchResults);
    } else {
      loadSearchQuotes();
    }
  }
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
  searchMode = false;
  searchResults = [];
  selectedSearchIndex = -1;
  document.getElementById('stock-search-input').value = '';
  document.getElementById('search-status').textContent = '';
  refreshMarketQuotes();
}
