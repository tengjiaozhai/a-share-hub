// 启动初始化（DOMContentLoaded 之前的 DOM 监听器）

document.getElementById('stock-search-input').addEventListener('keydown', event => {
  if (event.key === 'Enter') {
    searchStock();
  }
});

document.getElementById('market-select').addEventListener('change', event => {
  const input = document.getElementById('stock-search-input');
  if (event.target.value === 'us') {
    input.placeholder = '输入美股代码或名称（如：AAPL 或 苹果）';
  } else {
    input.placeholder = '输入股票代码或名称（如：600519 或 贵州茅台）';
  }
});

document.getElementById('cfg-add-stock').addEventListener('keydown', event => {
  if (event.key !== 'Enter') return;
  const value = event.target.value.trim();
  if (!value) return;
  const watchlistInput = document.getElementById('cfg-watchlist');
  const symbols = watchlistInput.value.split(',').map(s => s.trim()).filter(Boolean);
  if (!symbols.includes(value)) {
    symbols.push(value);
    watchlistInput.value = symbols.join(',');
  }
  event.target.value = '';
});

// 初始化回测日期为最近3个月
(function initBacktestDates() {
  const end = new Date();
  const start = new Date();
  start.setMonth(start.getMonth() - 3);
  const fmt = d => d.toISOString().split('T')[0];
  document.getElementById('cfg-bt-start').value = fmt(start);
  document.getElementById('cfg-bt-end').value = fmt(end);
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

  if ((event.ctrlKey || event.metaKey) && event.key === 'f') {
    const marketView = document.getElementById('view-market');
    if (marketView.classList.contains('active')) {
      event.preventDefault();
      document.getElementById('stock-search-input').focus();
    }
  }

  if (event.key === 'Escape' && isSearchMode) {
    exitSearchMode();
  }
});

loadDashboard();
updateModeStatus();
usInit();
setInterval(() => {
  if (!simRunning) {
    loadDashboard();
  }
}, 300000);
setInterval(() => {
  if (!simRunning && !isSearchMode) {
    refreshMarketQuotes();
  }
}, 30000);
