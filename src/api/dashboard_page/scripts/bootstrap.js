// 启动初始化（DOMContentLoaded 之前的 DOM 监听器）

// 初始化主题（从 data-theme 属性读取，由服务端注入）
(function initTheme() {
  var themeId = document.documentElement.getAttribute('data-theme') || 'trading-terminal';
  if (typeof initThemeFromServer === 'function') {
    initThemeFromServer(themeId);
  } else if (typeof applyTheme === 'function') {
    applyTheme(themeId);
  }
  if (typeof bindThemeSwitcher === 'function') {
    bindThemeSwitcher();
  }
})();

// ── 观察列表验证 ──

function validateWatchlistSymbols() {
  var marketEl = document.getElementById('cfg-market');
  var watchlistEl = document.getElementById('cfg-watchlist');
  if (!marketEl || !watchlistEl) return;

  var market = marketEl.value;
  var symbols = watchlistEl.value.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
  
  var mismatched = [];
  symbols.forEach(function(s) {
    var isUS = !s.endsWith('.SH') && !s.endsWith('.SZ');
    if (market === 'a' && isUS) {
      mismatched.push({ symbol: s, type: 'us' });
    } else if (market === 'us' && !isUS) {
      mismatched.push({ symbol: s, type: 'a' });
    }
  });

  var warningEl = document.getElementById('watchlist-warning');
  if (!warningEl) {
    warningEl = document.createElement('div');
    warningEl.id = 'watchlist-warning';
    warningEl.style.cssText = 'font-size:11px;color:var(--yellow);margin-top:4px;display:none;';
    watchlistEl.parentNode.insertBefore(warningEl, watchlistEl.nextSibling);
  }

  if (mismatched.length > 0) {
    var marketLabel = market === 'a' ? 'A股' : '美股';
    var mismatchedSymbols = mismatched.map(function(m) { return m.symbol; }).join(', ');
    var mismatchedTypes = mismatched.map(function(m) { return m.type === 'us' ? '美股' : 'A股'; }).join(', ');
    
    warningEl.innerHTML = '<span style="color:var(--yellow)">⚠️ ' + mismatchedSymbols + ' 是' + mismatchedTypes + '代码，当前市场为' + marketLabel + '，保存后刷新会被过滤。' +
      '<button onclick="switchMarketToMatch(\'' + mismatched[0].type + '\')" style="margin-left:8px;padding:2px 8px;font-size:11px;background:var(--accent);color:white;border:none;border-radius:4px;cursor:pointer;">切换到' + (mismatched[0].type === 'us' ? '美股' : 'A股') + '</button></span>';
    warningEl.style.display = 'block';
  } else {
    warningEl.style.display = 'none';
  }
}

function switchMarketToMatch(type) {
  var marketEl = document.getElementById('cfg-market');
  if (!marketEl) return;
  marketEl.value = type === 'us' ? 'us' : 'a';
  marketEl.dispatchEvent(new Event('change'));
}

// 初始化回测日期为最近3个月
(function initBacktestDates() {
  var endEl = document.getElementById('cfg-bt-end');
  if (!endEl) return;
  var startEl = document.getElementById('cfg-bt-start');
  if (!startEl) return;
  const end = new Date();
  const start = new Date();
  start.setMonth(start.getMonth() - 3);
  const fmt = d => d.toISOString().split('T')[0];
  startEl.value = fmt(start);
  endEl.value = fmt(end);
})();

// 工作台手动添加股票回车处理
(function initAddStockInput() {
  var input = document.getElementById('cfg-add-stock');
  if (!input) return;
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      var symbol = input.value.trim().toUpperCase();
      if (!symbol) return;
      if (addToWorkspaceWatchlist(symbol, symbol)) {
        input.value = '';
      }
    }
  });
})();

// 市场选择变化时过滤观察列表并刷新所有面板
(function initMarketFilter() {
  var marketEl = document.getElementById('cfg-market');
  if (!marketEl) return;
  marketEl.addEventListener('change', function() {
    filterWatchlistByMarket();
    validateWatchlistSymbols();
    loadDashboard();
  });
})();

// 观察列表输入时实时验证
(function initWatchlistValidation() {
  var watchlistEl = document.getElementById('cfg-watchlist');
  if (!watchlistEl) return;
  watchlistEl.addEventListener('input', function() {
    validateWatchlistSymbols();
  });
})();

// 区间表现对比 range pills 点击
(function initRangePills() {
  var container = document.getElementById('perf-range-pills');
  if (!container) return;
  container.addEventListener('click', function(e) {
    var btn = e.target.closest('.pill-btn');
    if (!btn) return;
    container.querySelectorAll('.pill-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    var market = document.getElementById('cfg-market')?.value || 'a';
    var window = btn.dataset.window || '30d';
    loadPerformancePanel(market, window);
  });
})();

document.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 's') {
    event.preventDefault();
    savePreferences();
  }

  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault();
    if (!simRunning) {
      triggerRun();
    }
  }

  if (event.key === 'Escape' && isCaseDrawerOpen()) {
    event.preventDefault();
    closeCaseDrawer();
  }
});

document.getElementById('drawer-backdrop')?.addEventListener('click', closeCaseDrawer);

loadDashboard();
updateModeStatus();
usInit();
marketInit();
setInterval(() => {
  if (!simRunning) {
    loadDashboard();
  }
}, 300000);
