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
