// 启动初始化（DOMContentLoaded 之前的 DOM 监听器）

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
    loadDashboard();
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
});

loadDashboard();
updateModeStatus();
usInit();
marketInit();
setInterval(() => {
  if (!simRunning) {
    loadDashboard();
  }
}, 300000);
