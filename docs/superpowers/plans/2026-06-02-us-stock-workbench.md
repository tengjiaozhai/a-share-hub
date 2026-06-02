# 美股交易工作台实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- []`) syntax for tracking.

**Goal:** 重构美股 Tab 为完整的交易工作台，复用现有工作台的三栏布局（左-策略配置、中-行情列表、右-资产与详情），集成全部美股相关接口。

**Architecture:** 将 `view_us_stock.html` 重构为与 `view_dashboard.html` 一致的三栏布局，左侧为搜索+自选管理+策略配置，中间为行情列表，右侧为币安资产+K线图+基本面详情。JS 层增加实时轮询、K线渲染、资产刷新。

**Tech Stack:** HTML/CSS/JS (内联), FastAPI, yfinance, Binance API

---

## 现有接口清单

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/v1/us-stock/quotes` | 批量获取自选股票行情 | ✅ 已实现 |
| GET | `/api/v1/us-stock/quote/{symbol}` | 单只股票实时行情 | ✅ 已实现 |
| GET | `/api/v1/us-stock/kline/{symbol}` | K 线历史数据 | ✅ 已实现 |
| GET | `/api/v1/us-stock/fundamental/{symbol}` | 基本面数据 | ✅ 已实现 |
| GET | `/api/v1/us-stock/search?q=xxx` | 搜索美股 | ✅ 已实现 |
| GET | `/api/v1/us-stock/watchlist` | 查询自选列表 | ✅ 已实现 |
| POST | `/api/v1/us-stock/watchlist` | 添加自选 | ✅ 已实现 |
| DELETE | `/api/v1/us-stock/watchlist/{symbol}` | 删除自选 | ✅ 已实现 |
| GET | `/api/v1/us-stock/binance/assets` | 查询币安账户美股资产 | ✅ 已实现 |

所有后端接口已就绪，本计划聚焦前端 Dashboard 重构。

---

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/api/dashboard_page/partials/view_us_stock.html` | 重写 | 三栏布局工作台 |
| `src/api/dashboard_page/scripts/us_stock.js` | 重写 | 完整交互逻辑 |
| `src/api/dashboard_page/styles/dashboard.css` | 修改 | 添加美股工作台样式 |

---

### Task 1: 重写 view_us_stock.html — 三栏布局

**Files:**
- Modify: `src/api/dashboard_page/partials/view_us_stock.html`

参考 `view_dashboard.html` 的三栏布局结构（panel-left / panel-center / panel-right），重写美股 tab。

- [ ] **Step 1: 读取现有布局参考**

读取 `src/api/dashboard_page/partials/view_dashboard.html` 了解三栏布局结构。

- [ ] **Step 2: 重写 view_us_stock.html**

```html
<div class="view" id="view-us-stock">
<div class="main">

  <!-- ── LEFT: 搜索 + 自选管理 + 策略配置 ── -->
  <div class="panel-left">
    <h2>美股工作台</h2>

    <div class="field">
      <label>搜索美股</label>
      <div style="display:flex;gap:6px">
        <input type="text" id="us-search-input" placeholder="输入代码或名称..." style="flex:1">
        <button onclick="usSearch()" style="padding:4px 10px;font-size:12px">搜索</button>
      </div>
      <div id="us-search-results" style="display:none;margin-top:6px;max-height:150px;overflow-y:auto"></div>
    </div>

    <div class="field">
      <label>自选管理</label>
      <div style="display:flex;gap:6px;margin-bottom:6px">
        <input type="text" id="us-add-symbol" placeholder="股票代码" style="flex:1">
        <button onclick="usAddManual()" style="padding:4px 10px;font-size:12px">+ 添加</button>
      </div>
      <div id="us-watchlist-chips" style="display:flex;flex-wrap:wrap;gap:4px;max-height:120px;overflow-y:auto"></div>
    </div>

    <div class="field">
      <label>交易时间</label>
      <div id="us-market-status" style="font-size:12px;color:var(--dim)">加载中...</div>
    </div>

    <div class="field">
      <label>数据刷新</label>
      <div style="display:flex;gap:6px;align-items:center">
        <span id="us-last-refresh" style="font-size:11px;color:var(--dim)">--</span>
        <button onclick="usLoadQuotes()" style="padding:2px 8px;font-size:11px">刷新</button>
      </div>
    </div>

    <div class="field">
      <label>币安连接</label>
      <div id="us-binance-status" style="font-size:12px;color:var(--dim)">检查中...</div>
    </div>
  </div>

  <!-- ── CENTER: 行情列表 ── -->
  <div class="panel-center">
    <div class="tabs">
      <button class="active" onclick="usSwitchCenterTab(this,'us-quotes-pane')">行情列表</button>
      <button onclick="usSwitchCenterTab(this,'us-kline-pane')">K线图</button>
      <button onclick="usSwitchCenterTab(this,'us-fundamental-pane')">基本面</button>
    </div>

    <div class="tab-pane active" id="us-quotes-pane">
      <div id="us-quotes-loading" style="color:var(--dim);padding:20px;text-align:center">加载中...</div>
      <table class="table" id="us-quotes-table" style="display:none">
        <thead>
          <tr>
            <th>代码</th><th>名称</th><th>最新价</th><th>涨跌额</th><th>涨跌幅</th>
            <th>开盘</th><th>最高</th><th>最低</th><th>成交量</th><th>市值</th><th>操作</th>
          </tr>
        </thead>
        <tbody id="us-quotes-body"></tbody>
      </table>
    </div>

    <div class="tab-pane" id="us-kline-pane">
      <div style="display:flex;gap:6px;margin-bottom:8px;align-items:center">
        <span style="font-size:12px;color:var(--dim)">周期:</span>
        <button class="us-kline-btn active" onclick="usSetKlineInterval(this,'1d','1mo')">日K</button>
        <button class="us-kline-btn" onclick="usSetKlineInterval(this,'1d','3mo')">3月</button>
        <button class="us-kline-btn" onclick="usSetKlineInterval(this,'1d','6mo')">6月</button>
        <button class="us-kline-btn" onclick="usSetKlineInterval(this,'1d','1y')">1年</button>
        <button class="us-kline-btn" onclick="usSetKlineInterval(this,'1wk','1y')">周K</button>
        <button class="us-kline-btn" onclick="usSetKlineInterval(this,'1mo','5y')">月K</button>
        <span id="us-kline-symbol" style="margin-left:auto;font-size:12px;color:var(--dim)">--</span>
      </div>
      <div id="us-kline-chart" style="min-height:300px;color:var(--dim);text-align:center;padding:40px">点击股票代码查看K线</div>
    </div>

    <div class="tab-pane" id="us-fundamental-pane">
      <div id="us-fundamental-content" style="padding:20px;color:var(--dim);text-align:center">点击股票代码查看基本面</div>
    </div>
  </div>

  <!-- ── RIGHT: 币安资产 + 详情 ── -->
  <div class="panel-right">
    <h3><i class="bi bi-wallet2"></i> 币安美股资产</h3>
    <div id="us-binance-assets" style="color:var(--dim);font-size:12px">加载中...</div>

    <h3 style="margin-top:16px"><i class="bi bi-info-circle"></i> 股票详情</h3>
    <div id="us-detail-summary" style="font-size:12px;color:var(--dim)">点击股票代码查看详情</div>
    <div id="us-detail-content" style="display:none"></div>

    <h3 style="margin-top:16px"><i class="bi bi-clock-history"></i> 最近搜索</h3>
    <div id="us-recent-searches" style="font-size:12px;color:var(--dim)">暂无</div>
  </div>

</div>
</div>
```

- [ ] **Step 3: 验证页面加载**

重启服务后访问 `http://127.0.0.1:8000/dashboard`，切换到美股 tab，确认三栏布局显示正常。

- [ ] **Step 4: 提交**

```bash
git add src/api/dashboard_page/partials/view_us_stock.html
git commit -m "feat(us_stock): rework dashboard tab to three-column workbench layout"
```

---

### Task 2: 重写 us_stock.js — 完整交互逻辑

**Files:**
- Modify: `src/api/dashboard_page/scripts/us_stock.js`

- [ ] **Step 1: 重写 us_stock.js**

```javascript
// ── 美股工作台 ──

let usCurrentSymbol = null;
let usCurrentInterval = '1d';
let usCurrentRange = '1mo';
let usRecentSearches = [];
let usRefreshTimer = null;

// ── 初始化 ──

function usInit() {
  usLoadQuotes();
  usLoadBinanceAssets();
  usUpdateMarketStatus();
  usLoadWatchlistChips();

  // 60s 轮询行情
  usRefreshTimer = setInterval(function() {
    usLoadQuotes();
    usLoadBinanceAssets();
  }, 60000);

  // 回车搜索
  var searchInput = document.getElementById('us-search-input');
  if (searchInput) {
    searchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') usSearch();
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
  var table = document.getElementById('us-quotes-table');
  var tbody = document.getElementById('us-quotes-body');

  fetch('/api/v1/us-stock/quotes')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var now = new Date();
      var el = document.getElementById('us-last-refresh');
      if (el) el.textContent = '更新于 ' + now.toLocaleTimeString();

      if (!data || data.length === 0) {
        if (loading) loading.textContent = '暂无自选股票，请在左侧添加';
        if (loading) loading.style.display = '';
        if (table) table.style.display = 'none';
        return;
      }
      if (loading) loading.style.display = 'none';
      if (table) table.style.display = '';
      if (tbody) {
        tbody.innerHTML = data.map(function(q) {
          var pct = q.change_pct || 0;
          var color = pct > 0 ? 'var(--green)' : pct < 0 ? 'var(--red)' : 'var(--dim)';
          var sign = pct > 0 ? '+' : '';
          var mcap = q.market_cap ? (q.market_cap / 1e9).toFixed(1) + 'B' : '-';
          var vol = q.volume ? (q.volume / 1e6).toFixed(1) + 'M' : '-';
          var chg = q.change ? (q.change > 0 ? '+' : '') + q.change.toFixed(2) : '-';
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
            '<td><button onclick="usRemoveWatchlist(\'' + q.symbol + '\')" style="color:var(--red);background:none;border:none;cursor:pointer;font-size:11px">删除</button></td>' +
            '</tr>';
        }).join('');
      }
    })
    .catch(function() {
      if (loading) loading.textContent = '加载失败，请检查网络';
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
      usLoadQuotes();
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

  // 切换到 K 线 tab
  var klineBtn = document.querySelector('#view-us-stock .tabs button:nth-child(2)');
  if (klineBtn) usSwitchCenterTab(klineBtn, 'us-kline-pane');

  // 加载 K 线
  usLoadKline();

  // 加载基本面
  usLoadFundamental();

  // 加载详情摘要
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
      if (!data || data.length === 0) {
        if (div) div.innerHTML = '<span style="color:var(--dim);font-size:11px">暂无资产（检查 BINANCE_API_KEY）</span>';
        if (statusEl) statusEl.innerHTML = '<span style="color:var(--dim)">未配置</span>';
        return;
      }
      if (statusEl) statusEl.innerHTML = '<span style="color:var(--green)">已连接</span>';

      var totalValue = 0;
      data.forEach(function(a) { totalValue += a.total; });

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

  // 夏令时: UTC 13:30-20:00 = 美东 9:30-16:00 = 北京 21:30-04:00
  // 冬令时: UTC 14:30-21:00 = 美东 9:30-16:00 = 北京 22:30-05:00
  var beijingHour = (utcHour + 8) % 24;

  if (isOpen) {
    el.innerHTML = '<span style="color:var(--green)">● 交易中</span> (美东 9:30-16:00 / 北京约 21:30-04:00)';
  } else if (isWeekday) {
    el.innerHTML = '<span style="color:var(--dim)">○ 已收盘</span> (下次开盘: 周一至周五 美东 9:30)';
  } else {
    el.innerHTML = '<span style="color:var(--dim)">○ 周末休市</span>';
  }
}
```

- [ ] **Step 2: 验证交互**

重启服务，访问 Dashboard 美股 tab：
- 左侧搜索框输入 "AAPL" 回车，确认搜索结果显示
- 点击搜索结果，确认添加到自选
- 中间行情列表加载
- 点击股票代码，切换到 K 线 tab，确认 K 线数据加载
- 切换到基本面 tab，确认基本面数据加载
- 右侧币安资产加载
- 右侧详情摘要更新

- [ ] **Step 3: 提交**

```bash
git add src/api/dashboard_page/scripts/us_stock.js
git commit -m "feat(us_stock): rework dashboard JS with full workbench interactions"
```

---

### Task 3: 补充 CSS 样式

**Files:**
- Modify: `src/api/dashboard_page/styles/dashboard.css`

- [ ] **Step 1: 读取现有 CSS**

读取 `src/api/dashboard_page/styles/dashboard.css`，了解现有的 `.main`, `.panel-left`, `.panel-center`, `.panel-right`, `.tabs`, `.tab-pane`, `.table` 等样式。

- [ ] **Step 2: 添加美股工作台专用样式**

在 CSS 文件末尾追加：

```css
/* ── 美股工作台 ── */
.us-kline-btn {
  padding: 2px 8px;
  font-size: 11px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 3px;
  cursor: pointer;
  color: var(--text);
}
.us-kline-btn.active,
.us-kline-btn:hover {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
#us-watchlist-chips a {
  text-decoration: none;
}
#us-watchlist-chips a:hover {
  text-decoration: underline;
}
```

- [ ] **Step 3: 验证样式**

重启服务，确认美股 tab 的按钮、表格、chips 样式正常。

- [ ] **Step 4: 提交**

```bash
git add src/api/dashboard_page/styles/dashboard.css
git commit -m "feat(us_stock): add workbench CSS styles for kline buttons and chips"
```

---

### Task 4: 全量验证

- [ ] **Step 1: 运行全部测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/us_stock/ -v
```

- [ ] **Step 2: 运行 lint**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m ruff check src/us_stock/ src/api/dashboard_page/
```

- [ ] **Step 3: 启动服务验证**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve
```

访问 `http://127.0.0.1:8000/dashboard`，切换美股 tab，验证：
- 三栏布局正确显示
- 搜索功能正常
- 自选管理（添加/删除）正常
- 行情列表加载
- K 线数据加载
- 基本面数据加载
- 币安资产显示
- 详情摘要更新

- [ ] **Step 4: 提交最终状态**

```bash
git add -A
git commit -m "feat(us_stock): complete US stock workbench with three-column layout"
```
