let usSearchResults = [];

function usLoadQuotes() {
  const loading = document.getElementById('us-quotes-loading');
  const table = document.getElementById('us-quotes-table');
  const tbody = document.getElementById('us-quotes-body');

  fetch('/api/v1/us-stock/quotes')
    .then(r => r.json())
    .then(data => {
      if (!data || data.length === 0) {
        loading.textContent = '暂无自选股票';
        loading.style.display = '';
        table.style.display = 'none';
        return;
      }
      loading.style.display = 'none';
      table.style.display = '';
      tbody.innerHTML = data.map(q => {
        const pct = q.change_pct || 0;
        const color = pct > 0 ? 'var(--green)' : pct < 0 ? 'var(--red)' : 'var(--dim)';
        const sign = pct > 0 ? '+' : '';
        const mcap = q.market_cap ? (q.market_cap / 1e9).toFixed(1) + 'B' : '-';
        const vol = q.volume ? (q.volume / 1e6).toFixed(1) + 'M' : '-';
        return `<tr>
          <td><a href="#" onclick="usShowDetail('${q.symbol}');return false">${q.symbol}</a></td>
          <td>${q.name || '-'}</td>
          <td>${q.price ? q.price.toFixed(2) : '-'}</td>
          <td style="color:${color}">${sign}${pct.toFixed(2)}%</td>
          <td>${vol}</td>
          <td>${mcap}</td>
          <td><button onclick="usRemoveWatchlist('${q.symbol}')" style="color:var(--red);background:none;border:none;cursor:pointer">删除</button></td>
        </tr>`;
      }).join('');
    })
    .catch(() => {
      loading.textContent = '加载失败';
    });
}

function usSearch() {
  const q = document.getElementById('us-search-input').value.trim();
  if (!q) return;
  fetch('/api/v1/us-stock/search?q=' + encodeURIComponent(q))
    .then(r => r.json())
    .then(data => {
      usSearchResults = data || [];
      const div = document.getElementById('us-search-results');
      if (usSearchResults.length === 0) {
        div.innerHTML = '<span style="color:var(--dim)">无结果</span>';
      } else {
        div.innerHTML = usSearchResults.map(s =>
          '<span style="display:inline-block;padding:4px 8px;margin:2px;border:1px solid var(--border);border-radius:4px;cursor:pointer" onclick="usSelectSearch(\'' + s.symbol + '\',\'' + (s.name||'') + '\')">' + s.symbol + ' - ' + (s.name||'') + '</span>'
        ).join('');
      }
      div.style.display = '';
    });
}

function usSelectSearch(symbol, name) {
  document.getElementById('us-search-input').value = symbol;
  window._usSelectedSymbol = symbol;
  window._usSelectedName = name;
}

function usAddFromSearch() {
  const symbol = window._usSelectedSymbol || document.getElementById('us-search-input').value.trim().toUpperCase();
  const name = window._usSelectedName || symbol;
  if (!symbol) return;
  fetch('/api/v1/us-stock/watchlist', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({symbol: symbol, name: name}),
  }).then(function(r) {
    if (r.ok) {
      usLoadQuotes();
      window._usSelectedSymbol = null;
      window._usSelectedName = null;
    } else {
      r.json().then(function(d) { alert(d.detail || '添加失败'); });
    }
  });
}

function usRemoveWatchlist(symbol) {
  if (!confirm('确认删除 ' + symbol + '？')) return;
  fetch('/api/v1/us-stock/watchlist/' + symbol, {method: 'DELETE'})
    .then(function(r) { if (r.ok) usLoadQuotes(); });
}

function usShowDetail(symbol) {
  var panel = document.getElementById('us-detail-panel');
  var title = document.getElementById('us-detail-title');
  var content = document.getElementById('us-detail-content');
  panel.style.display = '';
  title.textContent = symbol + ' 详情';
  content.innerHTML = '加载中...';

  Promise.all([
    fetch('/api/v1/us-stock/fundamental/' + symbol).then(function(r) { return r.json(); }),
    fetch('/api/v1/us-stock/kline/' + symbol + '?interval=1d&range=3mo').then(function(r) { return r.json(); }),
  ]).then(function(results) {
    var fund = results[0];
    var klines = results[1];
    var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px">';
    html += '<div>行业: ' + (fund.sector || '-') + '</div><div>细分: ' + (fund.industry || '-') + '</div>';
    html += '<div>市盈率: ' + (fund.pe_ratio ? fund.pe_ratio.toFixed(2) : '-') + '</div><div>市净率: ' + (fund.pb_ratio ? fund.pb_ratio.toFixed(2) : '-') + '</div>';
    html += '<div>股息率: ' + (fund.dividend_yield ? (fund.dividend_yield * 100).toFixed(2) + '%' : '-') + '</div><div>EPS: ' + (fund.eps ? fund.eps.toFixed(2) : '-') + '</div>';
    html += '<div>Beta: ' + (fund.beta ? fund.beta.toFixed(2) : '-') + '</div><div>52周高: ' + (fund.fifty_two_week_high ? fund.fifty_two_week_high.toFixed(2) : '-') + '</div>';
    html += '<div>52周低: ' + (fund.fifty_two_week_low ? fund.fifty_two_week_low.toFixed(2) : '-') + '</div>';
    html += '</div>';
    if (klines && klines.length > 0) {
      html += '<div style="max-height:200px;overflow-y:auto"><table class="table"><thead><tr><th>日期</th><th>开</th><th>高</th><th>低</th><th>收</th><th>量</th></tr></thead><tbody>';
      klines.slice(-10).forEach(function(k) {
        var dateStr = k.timestamp ? k.timestamp.split('T')[0] : '-';
        html += '<tr><td>' + dateStr + '</td><td>' + (k.open||0).toFixed(2) + '</td><td>' + (k.high||0).toFixed(2) + '</td><td>' + (k.low||0).toFixed(2) + '</td><td>' + (k.close||0).toFixed(2) + '</td><td>' + ((k.volume||0)/1e6).toFixed(1) + 'M</td></tr>';
      });
      html += '</tbody></table></div>';
    }
    content.innerHTML = html;
  }).catch(function() { content.innerHTML = '加载失败'; });
}

function usLoadBinanceAssets() {
  var div = document.getElementById('us-binance-assets');
  fetch('/api/v1/us-stock/binance/assets')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (!data || data.length === 0) {
        div.innerHTML = '<span style="color:var(--dim)">暂无币安资产数据（请检查 BINANCE_API_KEY 配置）</span>';
        return;
      }
      var html = '<table class="table"><thead><tr><th>资产</th><th>可用</th><th>冻结</th><th>总计</th></tr></thead><tbody>';
      data.forEach(function(a) {
        html += '<tr><td>' + a.symbol + '</td><td>' + a.free.toFixed(4) + '</td><td>' + a.locked.toFixed(4) + '</td><td>' + a.total.toFixed(4) + '</td></tr>';
      });
      html += '</tbody></table>';
      div.innerHTML = html;
    })
    .catch(function() { div.innerHTML = '加载失败'; });
}

function usInit() {
  usLoadQuotes();
  usLoadBinanceAssets();
  setInterval(usLoadQuotes, 60000);
  setInterval(usLoadBinanceAssets, 30000);
}
