// ── 美股工作台 ──

var usCurrentSymbol = null;
var usCurrentInterval = '1d';
var usCurrentRange = '1mo';
var usRecentSearches = [];
var usRefreshTimer = null;

// ── 行情分页状态 ──
var usQuotesAllData = [];
var usQuotesFilteredData = [];
var usQuotesPage = 1;
var usQuotesPageSize = 30;
var usQuotesSearchQuery = '';

// ── 全库搜索状态 ──
var usIsSearchMode = false;
var usSearchResults = [];

// ── 初始化 ──

function usInit() {
  usLoadQuotes();
  usLoadBinanceAssets();
  usUpdateMarketStatus();
  usLoadWatchlistChips();

  usRefreshTimer = setInterval(function() {
    usLoadQuotes();
    usLoadBinanceAssets();
  }, 60000);

  var searchInput = document.getElementById('us-search-input');
  if (searchInput) {
    searchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') usSearch();
    });
  }

  // 行情搜索框 - 支持回车全库搜索
  var quotesSearch = document.getElementById('us-quotes-search');
  if (quotesSearch) {
    quotesSearch.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') usQuotesSearchFull();
    });
    quotesSearch.addEventListener('input', function() {
      if (!this.value.trim()) {
        // 清空搜索，恢复正常模式
        usIsSearchMode = false;
        usSearchResults = [];
        usQuotesPage = 1;
        usFilterAndRenderQuotes();
      }
    });
  }
}

// ── Tab 切换 ──

function usSwitchCenterTab(btn, paneId) {
  btn.parentElement.querySelectorAll('button').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  document.querySelectorAll('#view-us-stock .tab-pane').forEach(function(p) { p.classList.remove('active'); });
  document.getElementById(paneId).classList.add('active');
}

// ── 行情加载 ──

function usLoadQuotes() {
  var loading = document.getElementById('us-quotes-loading');

  fetch('/api/v1/us-stock/quotes')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var now = new Date();
      var el = document.getElementById('us-last-refresh');
      if (el) el.textContent = '更新于 ' + now.toLocaleTimeString();

      usQuotesAllData = data || [];
      usFilterAndRenderQuotes();
    })
    .catch(function() {
      if (loading) loading.textContent = '加载失败，请检查网络';
    });
}

function usFilterAndRenderQuotes() {
  var loading = document.getElementById('us-quotes-loading');
  var table = document.getElementById('us-quotes-table');
  var tbody = document.getElementById('us-quotes-body');
  var countEl = document.getElementById('us-quotes-count');
  var paginationEl = document.getElementById('us-quotes-pagination');

  // 搜索模式下使用搜索结果
  if (usIsSearchMode) {
    usQuotesFilteredData = usSearchResults;
  } else if (usQuotesSearchQuery) {
    // 过滤模式下过滤自选列表
    usQuotesFilteredData = usQuotesAllData.filter(function(q) {
      var sym = (q.symbol || '').toLowerCase();
      var name = (q.name || '').toLowerCase();
      return sym.indexOf(usQuotesSearchQuery) !== -1 || name.indexOf(usQuotesSearchQuery) !== -1;
    });
  } else {
    usQuotesFilteredData = usQuotesAllData.slice();
  }

  // 更新计数
  if (countEl) {
    var total = usIsSearchMode ? usSearchResults.length : usQuotesAllData.length;
    countEl.textContent = usQuotesFilteredData.length + ' / ' + total + ' 只';
  }

  if (!usQuotesFilteredData || usQuotesFilteredData.length === 0) {
    if (loading) loading.textContent = usIsSearchMode ? '无匹配结果' : (usQuotesSearchQuery ? '无匹配结果' : '暂无自选股票，请在左侧添加');
    if (loading) loading.style.display = '';
    if (table) table.style.display = 'none';
    if (paginationEl) paginationEl.innerHTML = '';
    return;
  }

  if (loading) loading.style.display = 'none';
  if (table) table.style.display = '';

  // 分页
  var totalPages = Math.ceil(usQuotesFilteredData.length / usQuotesPageSize);
  if (usQuotesPage > totalPages) usQuotesPage = totalPages;
  if (usQuotesPage < 1) usQuotesPage = 1;
  var startIdx = (usQuotesPage - 1) * usQuotesPageSize;
  var pageData = usQuotesFilteredData.slice(startIdx, startIdx + usQuotesPageSize);

  // 渲染表格
  if (tbody) {
    tbody.innerHTML = pageData.map(function(q) {
      var pct = q.change_pct || 0;
      var color = pct > 0 ? 'var(--green)' : pct < 0 ? 'var(--red)' : 'var(--dim)';
      var sign = pct > 0 ? '+' : '';
      var mcap = q.market_cap ? (q.market_cap / 1e9).toFixed(1) + 'B' : '-';
      var vol = q.volume ? (q.volume / 1e6).toFixed(1) + 'M' : '-';
      var chg = q.change ? (q.change > 0 ? '+' : '') + q.change.toFixed(2) : '-';
      // 搜索模式下显示"添加"按钮，自选模式下显示"删除"按钮
      var inWatchlist = usQuotesAllData.some(function(item) { return item.symbol === q.symbol; });
      var actionBtn = usIsSearchMode
        ? (inWatchlist
          ? '<span style="color:var(--dim);font-size:11px">已添加</span>'
          : '<button onclick="usAddToWatchlist(\'' + q.symbol + '\',\'' + (q.name || '').replace(/'/g, "\\'") + '\')" style="color:var(--green);background:none;border:none;cursor:pointer;font-size:11px">+ 添加</button>')
        : '<button onclick="usRemoveWatchlist(\'' + q.symbol + '\')" style="color:var(--red);background:none;border:none;cursor:pointer;font-size:11px">删除</button>';
      return '<tr>' +
        '<td><a href="#" onclick="usSelectSymbol(\'' + q.symbol + '\');return false" style="font-weight:600">' + q.symbol + '</a></td>' +
        '<td>' + (q.name || '-') + '</td>' +
        '<td>' + (q.price ? q.price.toFixed(2) : '-') + '</td>' +
        '<td style="color:' + color + '">' + chg + '</td>' +
        '<td style="color:' + color + '">' + sign + pct.toFixed(2) + '%</td>' +
        '<td>' + (q.open ? q.open.toFixed(2) : '-') + '</td>' +
        '<td>' + (q.high ? q.high.toFixed(2) : '-') + '</td>' +
        '<td>' + (q.low ? q.low.toFixed(2) : '-') + '</td>' +
        '<td>' + vol + '</td>' +
        '<td>' + mcap + '</td>' +
        '<td>' + actionBtn + '</td>' +
        '</tr>';
    }).join('');
  }

  // 渲染分页
  if (paginationEl) {
    if (totalPages <= 1) {
      paginationEl.innerHTML = '';
      return;
    }
    var html = '';
    html += '<button class="us-page-btn" onclick="usGoToPage(1)" ' + (usQuotesPage === 1 ? 'disabled' : '') + '>&laquo;</button>';
    html += '<button class="us-page-btn" onclick="usGoToPage(' + (usQuotesPage - 1) + ')" ' + (usQuotesPage === 1 ? 'disabled' : '') + '>&lsaquo;</button>';
    html += '<span style="color:var(--muted)">' + usQuotesPage + ' / ' + totalPages + '</span>';
    html += '<button class="us-page-btn" onclick="usGoToPage(' + (usQuotesPage + 1) + ')" ' + (usQuotesPage === totalPages ? 'disabled' : '') + '>&rsaquo;</button>';
    html += '<button class="us-page-btn" onclick="usGoToPage(' + totalPages + ')" ' + (usQuotesPage === totalPages ? 'disabled' : '') + '>&raquo;</button>';
    paginationEl.innerHTML = html;
  }
}

function usGoToPage(page) {
  usQuotesPage = page;
  usFilterAndRenderQuotes();
  // 滚动到顶部
  var pane = document.getElementById('us-quotes-pane');
  if (pane) pane.scrollTop = 0;
}

// ── 中栏搜索全库 ──

function usQuotesSearchFull() {
  var query = document.getElementById('us-quotes-search').value.trim();
  if (!query) {
    // 清空搜索，恢复正常模式
    usIsSearchMode = false;
    usSearchResults = [];
    usQuotesPage = 1;
    usFilterAndRenderQuotes();
    return;
  }

  var loading = document.getElementById('us-quotes-loading');
  var table = document.getElementById('us-quotes-table');
  if (loading) {
    loading.textContent = '搜索全库中...';
    loading.style.display = '';
  }
  if (table) table.style.display = 'none';

  fetch('/api/v1/us-stock/search?q=' + encodeURIComponent(query))
    .then(function(r) { return r.json(); })
    .then(function(stocks) {
      if (!stocks || stocks.length === 0) {
        usIsSearchMode = false;
        usSearchResults = [];
        if (loading) loading.textContent = '未找到匹配的股票';
        return;
      }
      usIsSearchMode = true;
      usSearchResults = stocks;
      usQuotesPage = 1;
      usFilterAndRenderQuotes();
    })
    .catch(function() {
      if (loading) loading.textContent = '搜索失败';
    });
}

// ── 搜索 ──

function usSearch() {
  var q = document.getElementById('us-search-input').value.trim();
  if (!q) return;
  var resultsDiv = document.getElementById('us-search-results');
  if (resultsDiv) {
    resultsDiv.style.display = '';
    resultsDiv.innerHTML = '<span style="color:var(--dim)">搜索中...</span>';
  }

  fetch('/api/v1/us-stock/search?q=' + encodeURIComponent(q))
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!resultsDiv) return;
      if (!data || data.length === 0) {
        resultsDiv.innerHTML = '<span style="color:var(--dim)">无结果</span>';
        return;
      }
      resultsDiv.innerHTML = data.map(function(s) {
        return '<div style="padding:4px 6px;cursor:pointer;border-bottom:1px solid var(--border);font-size:12px" ' +
          'onclick="usSelectSearchResult(\'' + s.symbol + '\',\'' + (s.name || '').replace(/'/g, "\\'") + '\')">' +
          '<strong>' + s.symbol + '</strong> ' + (s.name || '') + ' <span style="color:var(--dim)">' + (s.exchange || '') + '</span></div>';
      }).join('');
    })
    .catch(function() {
      if (resultsDiv) resultsDiv.innerHTML = '<span style="color:var(--red)">搜索失败</span>';
    });
}

function usSelectSearchResult(symbol, name) {
  document.getElementById('us-search-input').value = symbol;
  document.getElementById('us-search-results').style.display = 'none';
  usAddToWatchlist(symbol, name || symbol);
  usAddRecentSearch(symbol);
}

function usAddRecentSearch(symbol) {
  usRecentSearches = usRecentSearches.filter(function(s) { return s !== symbol; });
  usRecentSearches.unshift(symbol);
  if (usRecentSearches.length > 10) usRecentSearches = usRecentSearches.slice(0, 10);
  var el = document.getElementById('us-recent-searches');
  if (el) {
    el.innerHTML = usRecentSearches.map(function(s) {
      return '<span style="display:inline-block;padding:2px 6px;margin:2px;border:1px solid var(--border);border-radius:3px;cursor:pointer;font-size:11px" onclick="usSelectSymbol(\'' + s + '\')">' + s + '</span>';
    }).join('');
  }
}

// ── 自选管理 ──

function usAddManual() {
  var input = document.getElementById('us-add-symbol');
  var symbol = (input.value || '').trim().toUpperCase();
  if (!symbol) return;
  usAddToWatchlist(symbol, symbol);
  input.value = '';
}

function usAddToWatchlist(symbol, name) {
  fetch('/api/v1/us-stock/watchlist', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({symbol: symbol, name: name}),
  }).then(function(r) {
    if (r.ok) {
      // 更新本地自选列表
      if (!usQuotesAllData.some(function(item) { return item.symbol === symbol; })) {
        usQuotesAllData.push({symbol: symbol, name: name});
      }
      usFilterAndRenderQuotes();
      usLoadWatchlistChips();
    } else {
      r.json().then(function(d) { alert(d.detail || '添加失败'); });
    }
  });
}

function usRemoveWatchlist(symbol) {
  if (!confirm('确认从自选删除 ' + symbol + '？')) return;
  fetch('/api/v1/us-stock/watchlist/' + symbol, {method: 'DELETE'})
    .then(function(r) {
      if (r.ok) {
        usLoadQuotes();
        usLoadWatchlistChips();
        if (usCurrentSymbol === symbol) {
          usCurrentSymbol = null;
          document.getElementById('us-kline-chart').innerHTML = '点击股票代码查看K线';
          document.getElementById('us-fundamental-content').innerHTML = '点击股票代码查看基本面';
          document.getElementById('us-detail-summary').textContent = '点击股票代码查看详情';
          document.getElementById('us-detail-content').style.display = 'none';
        }
      }
    });
}

function usLoadWatchlistChips() {
  fetch('/api/v1/us-stock/watchlist')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var el = document.getElementById('us-watchlist-chips');
      if (!el) return;
      if (!data || data.length === 0) {
        el.innerHTML = '<span style="font-size:11px;color:var(--dim)">暂无自选</span>';
        return;
      }
      el.innerHTML = data.map(function(item) {
        return '<span style="display:inline-flex;align-items:center;gap:4px;padding:2px 6px;border:1px solid var(--border);border-radius:3px;font-size:11px">' +
          '<a href="#" onclick="usSelectSymbol(\'' + item.symbol + '\');return false" style="color:var(--text);text-decoration:none">' + item.symbol + '</a>' +
          '<span style="color:var(--red);cursor:pointer" onclick="usRemoveWatchlist(\'' + item.symbol + '\')">&times;</span>' +
          '</span>';
      }).join('');
    });
}

// ── 股票选择 ──

function usSelectSymbol(symbol) {
  usCurrentSymbol = symbol;
  document.getElementById('us-kline-symbol').textContent = symbol;

  var klineBtn = document.querySelector('#view-us-stock .tabs button:nth-child(2)');
  if (klineBtn) usSwitchCenterTab(klineBtn, 'us-kline-pane');

  usLoadKline();
  usLoadFundamental();
  usLoadDetailSummary(symbol);
  usAddRecentSearch(symbol);
}

// ── K 线 ──

function usSetKlineInterval(btn, interval, range) {
  btn.parentElement.querySelectorAll('.us-kline-btn').forEach(function(b) { b.classList.remove('active'); });
  btn.classList.add('active');
  usCurrentInterval = interval;
  usCurrentRange = range;
  usLoadKline();
}

function usLoadKline() {
  if (!usCurrentSymbol) return;
  var chartDiv = document.getElementById('us-kline-chart');
  if (chartDiv) chartDiv.innerHTML = '<span style="color:var(--dim)">加载中...</span>';

  fetch('/api/v1/us-stock/kline/' + usCurrentSymbol + '?interval=' + usCurrentInterval + '&range=' + usCurrentRange)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data || data.length === 0) {
        if (chartDiv) chartDiv.innerHTML = '<span style="color:var(--dim)">无K线数据</span>';
        return;
      }
      usRenderKlineTable(chartDiv, data);
    })
    .catch(function() {
      if (chartDiv) chartDiv.innerHTML = '<span style="color:var(--red)">加载失败</span>';
    });
}

function usRenderKlineTable(container, klines) {
  var rows = klines.slice(-30);
  var html = '<div style="font-size:11px;color:var(--dim);margin-bottom:4px">最近 ' + rows.length + ' 根K线（共 ' + klines.length + ' 根）</div>';
  html += '<div style="max-height:350px;overflow-y:auto"><table class="table"><thead><tr>';
  html += '<th>日期</th><th>开</th><th>高</th><th>低</th><th>收</th><th>涨跌</th><th>成交量</th>';
  html += '</tr></thead><tbody>';

  rows.forEach(function(k, i) {
    var dateStr = k.timestamp ? k.timestamp.split('T')[0] : '-';
    var chg = i > 0 ? (k.close - rows[i-1].close) : 0;
    var chgPct = i > 0 && rows[i-1].close > 0 ? (chg / rows[i-1].close * 100) : 0;
    var color = chg > 0 ? 'var(--green)' : chg < 0 ? 'var(--red)' : 'var(--dim)';
    var vol = k.volume ? (k.volume / 1e6).toFixed(1) + 'M' : '-';
    html += '<tr>';
    html += '<td>' + dateStr + '</td>';
    html += '<td>' + (k.open || 0).toFixed(2) + '</td>';
    html += '<td>' + (k.high || 0).toFixed(2) + '</td>';
    html += '<td>' + (k.low || 0).toFixed(2) + '</td>';
    html += '<td style="font-weight:600">' + (k.close || 0).toFixed(2) + '</td>';
    html += '<td style="color:' + color + '">' + (chgPct > 0 ? '+' : '') + chgPct.toFixed(2) + '%</td>';
    html += '<td>' + vol + '</td>';
    html += '</tr>';
  });

  html += '</tbody></table></div>';
  if (container) container.innerHTML = html;
}

// ── 基本面 ──

function usLoadFundamental() {
  if (!usCurrentSymbol) return;
  var el = document.getElementById('us-fundamental-content');
  if (el) el.innerHTML = '<span style="color:var(--dim)">加载中...</span>';

  fetch('/api/v1/us-stock/fundamental/' + usCurrentSymbol)
    .then(function(r) { return r.json(); })
    .then(function(f) {
      if (!el) return;
      var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px">';
      html += usFundRow('行业', f.sector || '-');
      html += usFundRow('细分行业', f.industry || '-');
      html += usFundRow('市值', f.market_cap ? (f.market_cap / 1e9).toFixed(1) + 'B' : '-');
      html += usFundRow('市盈率 (PE)', f.pe_ratio ? f.pe_ratio.toFixed(2) : '-');
      html += usFundRow('市净率 (PB)', f.pb_ratio ? f.pb_ratio.toFixed(2) : '-');
      html += usFundRow('股息率', f.dividend_yield ? (f.dividend_yield * 100).toFixed(2) + '%' : '-');
      html += usFundRow('EPS', f.eps ? f.eps.toFixed(2) : '-');
      html += usFundRow('Beta', f.beta ? f.beta.toFixed(2) : '-');
      html += usFundRow('52周高', f.fifty_two_week_high ? f.fifty_two_week_high.toFixed(2) : '-');
      html += usFundRow('52周低', f.fifty_two_week_low ? f.fifty_two_week_low.toFixed(2) : '-');
      html += '</div>';
      el.innerHTML = html;
    })
    .catch(function() {
      if (el) el.innerHTML = '<span style="color:var(--red)">加载失败</span>';
    });
}

function usFundRow(label, value) {
  return '<div style="color:var(--dim)">' + label + '</div><div style="font-weight:500">' + value + '</div>';
}

// ── 详情摘要 ──

function usLoadDetailSummary(symbol) {
  var el = document.getElementById('us-detail-summary');
  var content = document.getElementById('us-detail-content');
  if (el) el.style.display = 'none';
  if (content) {
    content.style.display = '';
    content.innerHTML = '<span style="color:var(--dim)">加载中...</span>';
  }

  Promise.all([
    fetch('/api/v1/us-stock/quote/' + symbol).then(function(r) { return r.json(); }),
    fetch('/api/v1/us-stock/fundamental/' + symbol).then(function(r) { return r.json(); }),
  ]).then(function(results) {
    var q = results[0];
    var f = results[1];
    if (!content) return;
    var pct = q.change_pct || 0;
    var color = pct > 0 ? 'var(--green)' : pct < 0 ? 'var(--red)' : 'var(--dim)';
    var html = '<div style="font-size:12px">';
    html += '<div style="font-size:16px;font-weight:700;margin-bottom:4px">' + (q.name || symbol) + '</div>';
    html += '<div style="font-size:20px;font-weight:700;color:' + color + '">' + (q.price ? q.price.toFixed(2) : '-') + '</div>';
    html += '<div style="color:' + color + ';margin-bottom:8px">' + (pct > 0 ? '+' : '') + pct.toFixed(2) + '%</div>';
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px">';
    html += '<div style="color:var(--dim)">开盘</div><div>' + (q.open ? q.open.toFixed(2) : '-') + '</div>';
    html += '<div style="color:var(--dim)">最高</div><div>' + (q.high ? q.high.toFixed(2) : '-') + '</div>';
    html += '<div style="color:var(--dim)">最低</div><div>' + (q.low ? q.low.toFixed(2) : '-') + '</div>';
    html += '<div style="color:var(--dim)">昨收</div><div>' + (q.prev_close ? q.prev_close.toFixed(2) : '-') + '</div>';
    html += '<div style="color:var(--dim)">成交量</div><div>' + (q.volume ? (q.volume / 1e6).toFixed(1) + 'M' : '-') + '</div>';
    html += '<div style="color:var(--dim)">市值</div><div>' + (q.market_cap ? (q.market_cap / 1e9).toFixed(1) + 'B' : '-') + '</div>';
    html += '</div>';
    if (f && f.sector) {
      html += '<div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border)">';
      html += '<div style="color:var(--dim)">行业: ' + (f.sector || '-') + '</div>';
      html += '<div style="color:var(--dim)">PE: ' + (f.pe_ratio ? f.pe_ratio.toFixed(2) : '-') + ' | PB: ' + (f.pb_ratio ? f.pb_ratio.toFixed(2) : '-') + '</div>';
      html += '</div>';
    }
    html += '</div>';
    content.innerHTML = html;
  }).catch(function() {
    if (content) content.innerHTML = '<span style="color:var(--red)">加载失败</span>';
  });
}

// ── 币安资产 ──

function usLoadBinanceAssets() {
  var div = document.getElementById('us-binance-assets');
  var statusEl = document.getElementById('us-binance-status');

  fetch('/api/v1/us-stock/binance/assets')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (statusEl) statusEl.innerHTML = '<span style="color:var(--green)">已连接</span>';
      
      if (!data || data.length === 0) {
        if (div) div.innerHTML = '<span style="color:var(--dim);font-size:11px">暂无美股资产</span>';
        return;
      }

      var html = '<div style="margin-bottom:8px;font-size:13px;font-weight:600">共 ' + data.length + ' 种资产</div>';
      html += '<div style="max-height:200px;overflow-y:auto"><table class="table" style="font-size:11px"><thead><tr>';
      html += '<th>资产</th><th>可用</th><th>冻结</th><th>总计</th>';
      html += '</tr></thead><tbody>';

      data.forEach(function(a) {
        html += '<tr>';
        html += '<td style="font-weight:600">' + a.symbol + '</td>';
        html += '<td>' + a.free.toFixed(4) + '</td>';
        html += '<td>' + a.locked.toFixed(4) + '</td>';
        html += '<td>' + a.total.toFixed(4) + '</td>';
        html += '</tr>';
      });

      html += '</tbody></table></div>';
      if (div) div.innerHTML = html;
    })
    .catch(function() {
      if (div) div.innerHTML = '<span style="color:var(--red);font-size:11px">加载失败</span>';
      if (statusEl) statusEl.innerHTML = '<span style="color:var(--red)">连接失败</span>';
    });
}

// ── 市场状态 ──

function usUpdateMarketStatus() {
  var el = document.getElementById('us-market-status');
  if (!el) return;

  var now = new Date();
  var utcHour = now.getUTCHours();
  var utcMin = now.getUTCMinutes();
  var day = now.getUTCDay();
  var isWeekday = day >= 1 && day <= 5;
  var isMarketHours = (utcHour > 13 || (utcHour === 13 && utcMin >= 30)) && utcHour < 20;
  var isOpen = isWeekday && isMarketHours;

  if (isOpen) {
    el.innerHTML = '<span style="color:var(--green)">交易中</span> (美东 9:30-16:00 / 北京约 21:30-04:00)';
  } else if (isWeekday) {
    el.innerHTML = '<span style="color:var(--dim)">已收盘</span> (下次开盘: 周一至周五 美东 9:30)';
  } else {
    el.innerHTML = '<span style="color:var(--dim)">周末休市</span>';
  }
}
