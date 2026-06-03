// ── A 股工作台 ──

var aCurrentSymbol = null;
var aCurrentPeriod = 'daily';
var aRecentSearches = [];
var aRefreshTimer = null;

// ── 行情分页状态 ──
var aQuotesAllData = [];
var aQuotesFilteredData = [];
var aQuotesPage = 1;
var aQuotesPageSize = 30;
var aQuotesSearchQuery = '';

// ── 初始化 ──

function marketInit() {
  aLoadQuotes();
  aUpdateMarketStatus();
  aLoadWatchlistChips();

  aRefreshTimer = setInterval(function() {
    aLoadQuotes();
  }, 60000);

  var quotesSearch = document.getElementById('a-quotes-search');
  if (quotesSearch) {
    quotesSearch.addEventListener('input', function() {
      aQuotesSearchQuery = this.value.trim().toLowerCase();
      aQuotesPage = 1;
      aFilterAndRenderQuotes();
    });
    quotesSearch.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') aQuotesSearchFull();
    });
  }

  var searchInput = document.getElementById('a-search-input');
  if (searchInput) {
    searchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') aSearch();
    });
  }
}

// ── Tab 切换 ──

function aSwitchCenterTab(btn, paneId) {
  btn.parentElement.querySelectorAll('button').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  document.querySelectorAll('#view-market .tab-pane').forEach(function(p) { p.classList.remove('active'); });
  document.getElementById(paneId).classList.add('active');
}

// ── 行情加载 ──

function aLoadQuotes() {
  var loading = document.getElementById('a-quotes-loading');

  fetch('/api/v1/a-stock/watchlist')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data || data.length === 0) {
        aQuotesAllData = [];
        aFilterAndRenderQuotes();
        return;
      }
      // 只加载前 100 只股票的行情
      var symbols = data.slice(0, 100).map(function(item) { return item.symbol; });
      return fetch('/api/v1/a-stock/quotes', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(symbols),
      }).then(function(r) { return r.json(); });
    })
    .then(function(quotes) {
      var now = new Date();
      var el = document.getElementById('a-last-refresh');
      if (el) el.textContent = '更新于 ' + now.toLocaleTimeString();
      aQuotesAllData = quotes || [];
      aFilterAndRenderQuotes();
    })
    .catch(function() {
      if (loading) loading.textContent = '加载失败，请检查网络';
    });
}

function aFilterAndRenderQuotes() {
  var loading = document.getElementById('a-quotes-loading');
  var table = document.getElementById('a-quotes-table');
  var tbody = document.getElementById('a-quotes-body');
  var countEl = document.getElementById('a-quotes-count');
  var paginationEl = document.getElementById('a-quotes-pagination');

  if (aQuotesSearchQuery) {
    aQuotesFilteredData = aQuotesAllData.filter(function(q) {
      var sym = (q.symbol || '').toLowerCase();
      var name = (q.name || '').toLowerCase();
      return sym.indexOf(aQuotesSearchQuery) !== -1 || name.indexOf(aQuotesSearchQuery) !== -1;
    });
  } else {
    // 按换手率降序排列，热门股排在前面
    aQuotesFilteredData = aQuotesAllData.slice().sort(function(a, b) {
      return (parseFloat(b.turnover) || 0) - (parseFloat(a.turnover) || 0);
    });
  }

  if (countEl) {
    countEl.textContent = aQuotesFilteredData.length + ' / ' + aQuotesAllData.length + ' 只';
  }

  if (!aQuotesFilteredData || aQuotesFilteredData.length === 0) {
    if (loading) loading.textContent = aQuotesSearchQuery ? '无匹配结果' : '暂无自选股票，请在左侧添加';
    if (loading) loading.style.display = '';
    if (table) table.style.display = 'none';
    if (paginationEl) paginationEl.innerHTML = '';
    return;
  }

  if (loading) loading.style.display = 'none';
  if (table) table.style.display = '';

  var totalPages = Math.ceil(aQuotesFilteredData.length / aQuotesPageSize);
  if (aQuotesPage > totalPages) aQuotesPage = totalPages;
  if (aQuotesPage < 1) aQuotesPage = 1;
  var startIdx = (aQuotesPage - 1) * aQuotesPageSize;
  var pageData = aQuotesFilteredData.slice(startIdx, startIdx + aQuotesPageSize);

  if (tbody) {
    tbody.innerHTML = pageData.map(function(q) {
      var pct = parseFloat(q.change_pct) || 0;
      var color = pct > 0 ? 'var(--green)' : pct < 0 ? 'var(--red)' : 'var(--dim)';
      var sign = pct > 0 ? '+' : '';
      var close = parseFloat(q.close) || 0;
      var prevClose = parseFloat(q.prev_close) || 0;
      var chg = prevClose ? (close - prevClose).toFixed(2) : '-';
      var vol = q.volume ? (parseInt(q.volume) / 10000).toFixed(0) + '万' : '-';
      return '<tr>' +
        '<td><a href="#" onclick="aSelectSymbol(\'' + q.symbol + '\');return false" style="font-weight:600">' + (q.symbol || '') + '</a></td>' +
        '<td>' + (q.name || '-') + '</td>' +
        '<td>' + (close ? close.toFixed(2) : '-') + '</td>' +
        '<td style="color:' + color + '">' + chg + '</td>' +
        '<td style="color:' + color + '">' + sign + pct.toFixed(2) + '%</td>' +
        '<td>' + (parseFloat(q.open) || 0).toFixed(2) + '</td>' +
        '<td>' + (parseFloat(q.high) || 0).toFixed(2) + '</td>' +
        '<td>' + (parseFloat(q.low) || 0).toFixed(2) + '</td>' +
        '<td>' + vol + '</td>' +
        '<td>' + (parseFloat(q.turnover) || 0).toFixed(2) + '%</td>' +
        '<td><button onclick="aRemoveWatchlist(\'' + q.symbol + '\')" style="color:var(--red);background:none;border:none;cursor:pointer;font-size:11px">删除</button></td>' +
        '</tr>';
    }).join('');
  }

  if (paginationEl) {
    if (totalPages <= 1) {
      paginationEl.innerHTML = '';
      return;
    }
    var html = '';
    html += '<button class="us-page-btn" onclick="aGoToPage(1)" ' + (aQuotesPage === 1 ? 'disabled' : '') + '>&laquo;</button>';
    html += '<button class="us-page-btn" onclick="aGoToPage(' + (aQuotesPage - 1) + ')" ' + (aQuotesPage === 1 ? 'disabled' : '') + '>&lsaquo;</button>';
    html += '<span style="color:var(--muted)">' + aQuotesPage + ' / ' + totalPages + '</span>';
    html += '<button class="us-page-btn" onclick="aGoToPage(' + (aQuotesPage + 1) + ')" ' + (aQuotesPage === totalPages ? 'disabled' : '') + '>&rsaquo;</button>';
    html += '<button class="us-page-btn" onclick="aGoToPage(' + totalPages + ')" ' + (aQuotesPage === totalPages ? 'disabled' : '') + '>&raquo;</button>';
    paginationEl.innerHTML = html;
  }
}

function aGoToPage(page) {
  aQuotesPage = page;
  aFilterAndRenderQuotes();
}

// ── 中栏搜索全库 ──

function aQuotesSearchFull() {
  var query = document.getElementById('a-quotes-search').value.trim();
  if (!query) return;

  var loading = document.getElementById('a-quotes-loading');
  var table = document.getElementById('a-quotes-table');
  if (loading) {
    loading.textContent = '搜索全库中...';
    loading.style.display = '';
  }
  if (table) table.style.display = 'none';

  fetch('/api/v1/market/stocks?query=' + encodeURIComponent(query) + '&limit=100')
    .then(function(r) { return r.json(); })
    .then(function(stocks) {
      if (!stocks || stocks.length === 0) {
        if (loading) loading.textContent = '未找到匹配的股票';
        return;
      }
      var symbols = stocks.map(function(s) { return s.symbol; });
      return fetch('/api/v1/a-stock/quotes', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(symbols),
      }).then(function(r) { return r.json(); });
    })
    .then(function(quotes) {
      if (!quotes) return;
      aQuotesAllData = quotes;
      aQuotesFilteredData = quotes;
      aQuotesPage = 1;
      aFilterAndRenderQuotes();
    })
    .catch(function() {
      if (loading) loading.textContent = '搜索失败';
    });
}

// ── 搜索 ──

function aSearch() {
  var q = document.getElementById('a-search-input').value.trim();
  if (!q) return;
  var resultsDiv = document.getElementById('a-search-results');
  if (resultsDiv) {
    resultsDiv.style.display = '';
    resultsDiv.innerHTML = '<span style="color:var(--dim)">搜索中...</span>';
  }

  fetch('/api/v1/market/stocks?query=' + encodeURIComponent(q) + '&limit=20')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!resultsDiv) return;
      if (!data || data.length === 0) {
        resultsDiv.innerHTML = '<span style="color:var(--dim)">无结果</span>';
        return;
      }
      resultsDiv.innerHTML = data.map(function(s) {
        return '<div style="padding:4px 6px;cursor:pointer;border-bottom:1px solid var(--border);font-size:12px" ' +
          'onclick="aSelectSearchResult(\'' + s.symbol + '\',\'' + (s.name || '').replace(/'/g, "\\'") + '\')">' +
          '<strong>' + s.symbol + '</strong> ' + (s.name || '') + '</div>';
      }).join('');
    })
    .catch(function() {
      if (resultsDiv) resultsDiv.innerHTML = '<span style="color:var(--red)">搜索失败</span>';
    });
}

function aSelectSearchResult(symbol, name) {
  document.getElementById('a-search-input').value = symbol;
  document.getElementById('a-search-results').style.display = 'none';
  aAddToWatchlist(symbol, name || symbol);
  aAddRecentSearch(symbol);
}

function aAddRecentSearch(symbol) {
  aRecentSearches = aRecentSearches.filter(function(s) { return s !== symbol; });
  aRecentSearches.unshift(symbol);
  if (aRecentSearches.length > 10) aRecentSearches = aRecentSearches.slice(0, 10);
  var el = document.getElementById('a-recent-searches');
  if (el) {
    el.innerHTML = aRecentSearches.map(function(s) {
      return '<span style="display:inline-block;padding:2px 6px;margin:2px;border:1px solid var(--border);border-radius:3px;cursor:pointer;font-size:11px" onclick="aSelectSymbol(\'' + s + '\')">' + s + '</span>';
    }).join('');
  }
}

// ── 自选管理 ──

function aAddManual() {
  var input = document.getElementById('a-add-symbol');
  var symbol = (input.value || '').trim().toUpperCase();
  if (!symbol) return;
  aAddToWatchlist(symbol, symbol);
  input.value = '';
}

function aAddToWatchlist(symbol, name) {
  fetch('/api/v1/a-stock/watchlist', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({symbol: symbol, name: name}),
  }).then(function(r) {
    if (r.ok) {
      aLoadQuotes();
      aLoadWatchlistChips();
    } else {
      r.json().then(function(d) { alert(d.detail || '添加失败'); });
    }
  });
}

function aRemoveWatchlist(symbol) {
  if (!confirm('确认从自选删除 ' + symbol + '？')) return;
  fetch('/api/v1/a-stock/watchlist/' + symbol, {method: 'DELETE'})
    .then(function(r) {
      if (r.ok) {
        aLoadQuotes();
        aLoadWatchlistChips();
      }
    });
}

function aLoadWatchlistChips() {
  fetch('/api/v1/a-stock/watchlist')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var el = document.getElementById('a-watchlist-chips');
      if (!el) return;
      if (!data || data.length === 0) {
        el.innerHTML = '<span style="font-size:11px;color:var(--dim)">暂无自选</span>';
        return;
      }
      el.innerHTML = data.map(function(item) {
        return '<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 6px;border:1px solid var(--border);border-radius:3px;font-size:11px">' +
          '<a href="#" onclick="aSelectSymbol(\'' + item.symbol + '\');return false" style="color:var(--text);text-decoration:none">' + item.symbol + '</a>' +
          '<span style="color:var(--red);cursor:pointer" onclick="aRemoveWatchlist(\'' + item.symbol + '\')">&times;</span>' +
          '</span>';
      }).join('');
    });
}

// ── 股票选择 ──

function aSelectSymbol(symbol) {
  aCurrentSymbol = symbol;
  document.getElementById('a-kline-symbol').textContent = symbol;

  var klineBtn = document.querySelector('#view-market .tabs button:nth-child(2)');
  if (klineBtn) aSwitchCenterTab(klineBtn, 'a-kline-pane');

  aLoadKline();
  aLoadFundamental();
  aLoadDetailSummary(symbol);
  aAddRecentSearch(symbol);
}

// ── K 线 ──

function aSetKlinePeriod(btn, period) {
  btn.parentElement.querySelectorAll('.us-kline-btn').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  aCurrentPeriod = period;
  aLoadKline();
}

function aLoadKline() {
  if (!aCurrentSymbol) return;
  var chartDiv = document.getElementById('a-kline-chart');
  if (chartDiv) chartDiv.innerHTML = '<span style="color:var(--dim)">加载中...</span>';

  fetch('/api/v1/a-stock/kline/' + aCurrentSymbol + '?period=' + aCurrentPeriod + '&count=60')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data || data.length === 0) {
        if (chartDiv) chartDiv.innerHTML = '<span style="color:var(--dim)">无K线数据</span>';
        return;
      }
      aRenderKlineTable(chartDiv, data);
    })
    .catch(function() {
      if (chartDiv) chartDiv.innerHTML = '<span style="color:var(--red)">加载失败</span>';
    });
}

function aRenderKlineTable(container, klines) {
  var rows = klines.slice(-30);
  var html = '<div style="font-size:11px;color:var(--dim);margin-bottom:4px">最近 ' + rows.length + ' 根K线（共 ' + klines.length + ' 根）</div>';
  html += '<div style="max-height:350px;overflow-y:auto"><table class="table"><thead><tr>';
  html += '<th>日期</th><th>开</th><th>高</th><th>低</th><th>收</th><th>涨跌</th><th>成交量</th>';
  html += '</tr></thead><tbody>';

  rows.forEach(function(k, i) {
    var chg = i > 0 ? (k.close - rows[i-1].close) : 0;
    var chgPct = i > 0 && rows[i-1].close > 0 ? (chg / rows[i-1].close * 100) : 0;
    var color = chg > 0 ? 'var(--green)' : chg < 0 ? 'var(--red)' : 'var(--dim)';
    var vol = k.volume ? (k.volume / 10000).toFixed(0) + '万' : '-';
    html += '<tr>';
    html += '<td>' + k.date + '</td>';
    html += '<td>' + k.open.toFixed(2) + '</td>';
    html += '<td>' + k.high.toFixed(2) + '</td>';
    html += '<td>' + k.low.toFixed(2) + '</td>';
    html += '<td style="font-weight:600">' + k.close.toFixed(2) + '</td>';
    html += '<td style="color:' + color + '">' + (chgPct > 0 ? '+' : '') + chgPct.toFixed(2) + '%</td>';
    html += '<td>' + vol + '</td>';
    html += '</tr>';
  });

  html += '</tbody></table></div>';
  if (container) container.innerHTML = html;
}

// ── 基本面 ──

function aLoadFundamental() {
  if (!aCurrentSymbol) return;
  var el = document.getElementById('a-fundamental-content');
  if (el) el.innerHTML = '<span style="color:var(--dim)">加载中...</span>';

  fetch('/api/v1/a-stock/fundamental/' + aCurrentSymbol)
    .then(function(r) { return r.json(); })
    .then(function(f) {
      if (!el) return;
      var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px">';
      html += aFundRow('股票代码', f.symbol || '-');
      html += aFundRow('名称', f.name || '-');
      html += aFundRow('市盈率 (PE)', f.pe_ratio ? f.pe_ratio.toFixed(2) : '-');
      html += aFundRow('换手率', f.turnover ? f.turnover.toFixed(2) + '%' : '-');
      html += aFundRow('振幅', f.amplitude ? f.amplitude.toFixed(2) + '%' : '-');
      html += aFundRow('量比', f.volume_ratio ? f.volume_ratio.toFixed(2) : '-');
      html += '</div>';
      el.innerHTML = html;
    })
    .catch(function() {
      if (el) el.innerHTML = '<span style="color:var(--red)">加载失败</span>';
    });
}

function aFundRow(label, value) {
  return '<div style="color:var(--dim)">' + label + '</div><div style="font-weight:500">' + value + '</div>';
}

// ── 详情摘要 ──

function aLoadDetailSummary(symbol) {
  var el = document.getElementById('a-detail-summary');
  var content = document.getElementById('a-detail-content');
  if (el) el.style.display = 'none';
  if (content) {
    content.style.display = '';
    content.innerHTML = '<span style="color:var(--dim)">加载中...</span>';
  }

  fetch('/api/v1/a-stock/fundamental/' + symbol)
    .then(function(r) { return r.json(); })
    .then(function(f) {
      if (!content) return;
      var html = '<div style="font-size:12px">';
      html += '<div style="font-size:16px;font-weight:700;margin-bottom:4px">' + (f.name || symbol) + '</div>';
      html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px">';
      html += '<div style="color:var(--dim)">代码</div><div>' + (f.symbol || '-') + '</div>';
      html += '<div style="color:var(--dim)">PE</div><div>' + (f.pe_ratio ? f.pe_ratio.toFixed(2) : '-') + '</div>';
      html += '<div style="color:var(--dim)">换手率</div><div>' + (f.turnover ? f.turnover.toFixed(2) + '%' : '-') + '</div>';
      html += '<div style="color:var(--dim)">振幅</div><div>' + (f.amplitude ? f.amplitude.toFixed(2) + '%' : '-') + '</div>';
      html += '<div style="color:var(--dim)">量比</div><div>' + (f.volume_ratio ? f.volume_ratio.toFixed(2) : '-') + '</div>';
      html += '</div>';
      html += '</div>';
      content.innerHTML = html;
    })
    .catch(function() {
      if (content) content.innerHTML = '<span style="color:var(--red)">加载失败</span>';
    });
}

// ── 市场状态 ──

function aUpdateMarketStatus() {
  var el = document.getElementById('a-market-status');
  if (!el) return;

  var now = new Date();
  var hour = now.getHours();
  var min = now.getMinutes();
  var day = now.getDay();
  var isWeekday = day >= 1 && day <= 5;
  var timeNum = hour * 100 + min;
  var isMarketHours = (timeNum >= 930 && timeNum <= 1130) || (timeNum >= 1300 && timeNum <= 1500);
  var isOpen = isWeekday && isMarketHours;

  if (isOpen) {
    el.innerHTML = '<span style="color:var(--green)">交易中</span> (9:30-11:30 / 13:00-15:00)';
  } else if (isWeekday) {
    el.innerHTML = '<span style="color:var(--dim)">已收盘</span> (下次开盘: 周一至周五 9:30)';
  } else {
    el.innerHTML = '<span style="color:var(--dim)">周末休市</span>';
  }
}
