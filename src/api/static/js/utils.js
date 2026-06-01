// src/api/static/js/utils.js

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
  return n.toLocaleString('zh-CN', { style: 'currency', currency: 'CNY' });
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
  const pct = (n * 100).toFixed(1);
  return n >= 0 ? `+${pct}%` : `${pct}%`;
}

function formatVolume(raw) {
  if (raw === null || raw === undefined || raw === '') return '--';
  const n = Number(raw);
  if (!Number.isFinite(n)) return normalizeText(raw);
  if (n >= 1e8) return `${(n / 1e8).toFixed(2)}亿`;
  if (n >= 1e4) return `${(n / 1e4).toFixed(2)}万`;
  return n.toFixed(0);
}

function toList(value) {
  if (Array.isArray(value)) return value;
  if (value === null || value === undefined) return [];
  return [value];
}

function serviceDotClass(status) {
  if (status === 'ok' || status === 'running') return 'dot-green';
  if (status === 'error' || status === 'stopped') return 'dot-red';
  return 'dot-yellow';
}

function toAlertLevel(level) {
  if (level === 'critical' || level === 'error') return 'error';
  if (level === 'warning') return 'warning';
  return 'info';
}

function extractErrorMessage(body, fallback) {
  if (typeof body === 'string') return body;
  if (body && body.detail) return body.detail;
  if (body && body.message) return body.message;
  return fallback;
}

function setButtonLoading(btn, loading, originalText) {
  if (loading) {
    btn.disabled = true;
    btn.dataset.originalText = btn.textContent;
    btn.innerHTML = '<span class="loading-spinner"></span> 加载中...';
  } else {
    btn.disabled = false;
    btn.textContent = btn.dataset.originalText || originalText;
  }
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.classList.add('show'), 10);
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}
