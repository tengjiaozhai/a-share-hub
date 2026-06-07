// 共享状态变量（必须在 dashboard.js / market.js / alpha.js / bootstrap.js 之前声明）
let execMode = 'full';
let simRunning = false;
let killSwitchActive = false;
let configHydrated = false;
let _savePrefsTimer = null;
let scanRunning = false;
let btRunning = false;
let searchResults = [];
let selectedSearchIndex = -1;
let isSearchMode = false;

const PAGE_SIZE = 20;
const pag = {
  decisions: { page: 0, data: [] },
  orders:    { page: 0, data: [] },
  targets:   { page: 0, data: [] },
  errors:    { page: 0, data: [] },
};

function pagSlice(key) {
  const p = pag[key];
  const start = p.page * PAGE_SIZE;
  return p.data.slice(start, start + PAGE_SIZE);
}

function pagTotal(key) {
  return Math.max(1, Math.ceil(pag[key].data.length / PAGE_SIZE));
}

function pagPrev(key) {
  if (pag[key].page > 0) { pag[key].page--; renderPagTab(key); }
}

function pagNext(key) {
  if (pag[key].page < pagTotal(key) - 1) { pag[key].page++; renderPagTab(key); }
}

function renderPagControls(key) {
  const total = pagTotal(key);
  const cur = pag[key].page + 1;
  return `<div class="pagination">
    <button onclick="pagPrev('${key}')" ${cur <= 1 ? 'disabled' : ''}>上一页</button>
    <span class="page-info">${cur} / ${total}</span>
    <button onclick="pagNext('${key}')" ${cur >= total ? 'disabled' : ''}>下一页</button>
  </div>`;
}

function renderPagTab(key) {
  const renderers = { decisions: renderDecisions, orders: renderOrders, targets: renderTargets, errors: renderErrorEvents };
  if (renderers[key]) renderers[key](pag[key].data);
}

function normalizeText(value, fallback = '--') {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text ? text : fallback;
}

function pickFirst(obj, keys, fallback = null) {
  for (const key of keys) {
    if (obj && obj[key] !== null && obj[key] !== undefined && obj[key] !== '') {
      return obj[key];
    }
  }
  return fallback;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatDate(raw) {
  const value = normalizeText(raw, '');
  if (!value) return '--';
  return value.includes('T') ? value.split('T')[0] : value.slice(0, 10);
}

function formatTime(raw) {
  const value = normalizeText(raw, '');
  if (!value) return '--';
  if (value.includes('T')) {
    const time = value.split('T')[1] || '';
    return time.split('.')[0] || '--';
  }
  if (value.includes(' ')) {
    return value.split(' ')[1] || value;
  }
  return value.length > 8 ? value.slice(0, 8) : value;
}

function formatPercent(raw) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  return `${(n * 100).toFixed(1)}%`;
}

function formatConfidence(raw) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  const pct = n <= 1 ? n * 100 : n;
  return `${pct.toFixed(0)}%`;
}

function formatCurrency(raw) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  const sign = n > 0 ? '+' : '';
  return `${sign}CNY ${n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatNumber(raw, digits = 2) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  return n.toFixed(digits);
}

function formatSignedPercent(raw) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
}

function formatVolume(raw) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  return n.toLocaleString('zh-CN');
}

function toList(value) {
  return Array.isArray(value) ? value : [];
}

function serviceDotClass(status) {
  const normalized = normalizeText(status, '').toLowerCase();
  if (normalized === 'ok' || normalized === 'healthy' || normalized === 'active') return 'dot g';
  if (normalized === 'warning' || normalized === 'warn' || normalized === 'degraded' || normalized === 'unknown') return 'dot y';
  return 'dot r';
}

function toAlertLevel(level) {
  const normalized = normalizeText(level, '').toLowerCase();
  if (normalized === 'warning' || normalized === 'warn') return 'warn';
  if (normalized === 'error' || normalized === 'err' || normalized === 'critical' || normalized === 'fatal') return 'err';
  return 'info';
}

async function parseResponseBody(res) {
  const text = await res.text();
  if (!text) return '';
  try {
    return JSON.parse(text);
  } catch (_) {
    return text;
  }
}

function extractErrorMessage(body, fallback) {
  if (!body) return fallback;
  if (typeof body === 'string') return body;
  return normalizeText(body.detail || body.message || body.error, fallback);
}
