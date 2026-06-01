const State = {
  execMode: 'full',
  killSwitch: false,
  configHydrated: false,
  simRunning: false,
  pagination: {
    decisions: { page: 0, data: [] },
    orders:    { page: 0, data: [] },
    targets:   { page: 0, data: [] },
    errors:    { page: 0, data: [] },
  },
  PAGE_SIZE: 10,
};

function pagSlice(key) {
  const p = State.pagination[key];
  const start = p.page * State.PAGE_SIZE;
  return p.data.slice(start, start + State.PAGE_SIZE);
}

function pagTotal(key) {
  return Math.max(1, Math.ceil(State.pagination[key].data.length / State.PAGE_SIZE));
}

function pagPrev(key) {
  if (State.pagination[key].page > 0) {
    State.pagination[key].page--;
    renderPagTab(key);
  }
}

function pagNext(key) {
  if (State.pagination[key].page < pagTotal(key) - 1) {
    State.pagination[key].page++;
    renderPagTab(key);
  }
}

function renderPagControls(key) {
  const total = pagTotal(key);
  const cur = State.pagination[key].page + 1;
  return `<div class="pagination">
    <button onclick="pagPrev('${key}')" ${cur <= 1 ? 'disabled' : ''}>上一页</button>
    <span class="page-info">${cur} / ${total}</span>
    <button onclick="pagNext('${key}')" ${cur >= total ? 'disabled' : ''}>下一页</button>
  </div>`;
}

function renderPagTab(key) {
  const renderers = {
    decisions: renderDecisions,
    orders: renderOrders,
    targets: renderTargets,
    errors: renderErrorEvents,
  };
  if (renderers[key]) renderers[key](State.pagination[key].data);
}

// 配置状态
const ConfigState = {
  capital: 100,
  watchlist: ['600519.SH', '000858.SZ', '601318.SH'],
  maxPosition: 20,
  stopLoss: -5,
  maxDailyLoss: -3,
  mode: 'mock',
  allowNewPosition: true,
  execMode: 'full'
};

// 更新配置
function updateConfig(key, value) {
  ConfigState[key] = value;
  console.log('Config updated: ' + key + ' = ' + value);
}

// 获取配置
function getConfig() {
  return { ...ConfigState };
}

// 从表单同步配置
function syncConfigFromForm() {
  var capitalEl = document.getElementById('cfg-capital');
  if (capitalEl) ConfigState.capital = parseInt(capitalEl.value) || 100;

  var watchlistEl = document.getElementById('cfg-watchlist');
  if (watchlistEl) {
    ConfigState.watchlist = watchlistEl.value.split(',').map(function(s) { return s.trim(); }).filter(function(s) { return s; });
  }

  var maxPosEl = document.getElementById('cfg-max-pos');
  if (maxPosEl) ConfigState.maxPosition = parseInt(maxPosEl.value) || 20;

  var stopLossEl = document.getElementById('cfg-stop-loss');
  if (stopLossEl) ConfigState.stopLoss = parseFloat(stopLossEl.value) || -5;

  var maxDailyEl = document.getElementById('cfg-max-daily');
  if (maxDailyEl) ConfigState.maxDailyLoss = parseFloat(maxDailyEl.value) || -3;

  var modeEl = document.getElementById('cfg-mode');
  if (modeEl) ConfigState.mode = modeEl.value || 'mock';

  var newPosEl = document.getElementById('cfg-new-pos');
  if (newPosEl) ConfigState.allowNewPosition = newPosEl.classList.contains('on');
}
