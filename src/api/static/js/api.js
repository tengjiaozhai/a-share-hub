const API_BASE = '/api/v1';

async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }
  return res.json();
}

const AlphaAPI = {
  getAssets:       ()         => apiFetch('/alpha/assets'),
  getTickets:      ()         => apiFetch('/alpha/tickets'),
  createTicket:    (data)     => apiFetch('/alpha/tickets', { method: 'POST', body: JSON.stringify(data) }),
  approveTicket:   (id)       => apiFetch(`/alpha/tickets/${id}/approve`, { method: 'POST' }),
  createFill:      (id, data) => apiFetch(`/alpha/tickets/${id}/fills`, { method: 'POST', body: JSON.stringify(data) }),
  getCapabilities: ()         => apiFetch('/alpha/capabilities'),
  getWorkbench:    ()         => apiFetch('/dashboard/workbench'),
  getWatchlist:    ()         => apiFetch('/alpha/watchlist'),
  addWatchlist:    (data)     => apiFetch('/alpha/watchlist', { method: 'POST', body: JSON.stringify(data) }),
  scanResearch:    ()         => apiFetch('/alpha/research/scan', { method: 'POST' }),
  proposeTicket:   (data)     => apiFetch('/alpha/research/propose-top-ticket', { method: 'POST', body: JSON.stringify(data) }),
};

const MarketAPI = {
  getQuote:    (symbol) => apiFetch(`/market/quote/${symbol}`),
  getBulk:     (symbols) => apiFetch('/market/bulk', { method: 'POST', body: JSON.stringify(symbols) }),
  search:      (query) => apiFetch(`/market/search?q=${encodeURIComponent(query)}`),
};

const DashboardAPI = {
  getWorkbench:    ()         => apiFetch('/dashboard/workbench'),
  runDecision:     (payload)  => apiFetch('/dashboard/run', { method: 'POST', body: JSON.stringify(payload) }),
  getKillSwitch:   ()         => apiFetch('/kill-switch/status'),
  activateKill:    ()         => apiFetch('/kill-switch/activate', { method: 'POST' }),
  deactivateKill:  ()         => apiFetch('/kill-switch/deactivate', { method: 'POST' }),
};

// 配置保存 API
const CONFIG_API = '/api/v1/dashboard/config';
const RUN_API = '/api/v1/dashboard/run';
const BACKTEST_API = '/api/v1/dashboard/backtest';
const SCAN_API = '/api/v1/dashboard/scan';

// 保存配置
async function saveConfig(config) {
  const response = await fetch(CONFIG_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });
  return await parseResponseBody(response);
}

// 运行模拟
async function runSimulation() {
  const response = await fetch(RUN_API, { method: 'POST' });
  return await parseResponseBody(response);
}

// 运行回测
async function runBacktest(startDate, endDate) {
  const response = await fetch(BACKTEST_API, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ start_date: startDate, end_date: endDate })
  });
  return await parseResponseBody(response);
}

// 运行扫描
async function runScan() {
  const response = await fetch(SCAN_API, { method: 'POST' });
  return await parseResponseBody(response);
}
