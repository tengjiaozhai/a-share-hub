// src/api/static/js/views/alpha.js

function initAlpha() {
  const ticketForm = document.getElementById('alpha-ticket-form');
  if (ticketForm) {
    ticketForm.addEventListener('submit', submitAlphaTicket);
  }
}

function renderAlpha() {
  loadAlphaAssets();
  loadAlphaTickets();
  loadAlphaWatchlist();
  loadAlphaCapabilities();
}

async function loadAlphaAssets() {
  const root = document.getElementById('alpha-assets');
  if (!root) return;
  try {
    const data = await AlphaAPI.getAssets();
    if (!data.items || data.items.length === 0) {
      root.innerHTML = '<span style="color:var(--dim)">暂无资产数据</span>';
      return;
    }
    root.innerHTML = data.items.map(asset => `
      <div class="asset-row">
        <strong>${escapeHtml(asset.symbol)}</strong>
        <span>${escapeHtml(asset.underlying_symbol)}</span>
        <span>${escapeHtml(asset.market_status)}</span>
        <span>${escapeHtml(asset.asset_status)}</span>
      </div>
    `).join('');
  } catch (err) {
    root.innerHTML = '<span style="color:var(--danger)">加载失败</span>';
  }
}

async function loadAlphaTickets() {
  const root = document.getElementById('alpha-tickets');
  if (!root) return;
  try {
    const data = await AlphaAPI.getTickets();
    if (!data.items || data.items.length === 0) {
      root.innerHTML = '<span style="color:var(--dim)">暂无建议单</span>';
      return;
    }
    renderAlphaTickets(data.items);
  } catch (err) {
    root.innerHTML = '<span style="color:var(--danger)">加载失败</span>';
  }
}

function renderAlphaTickets(items) {
  const root = document.getElementById('alpha-tickets');
  if (!root) return;
  root.innerHTML = items.map(item => `
    <div class="ticket-row">
      <strong>${escapeHtml(item.asset_symbol)}</strong>
      <span>${escapeHtml(item.action)}</span>
      <span>${escapeHtml(String(item.suggested_quantity))}</span>
      <span>@ ${escapeHtml(String(item.suggested_limit_price))}</span>
      <span>${escapeHtml(item.status)}</span>
    </div>
  `).join('');
}

async function submitAlphaTicket(event) {
  event.preventDefault();
  const btn = event.target.querySelector('button[type="submit"]');
  setButtonLoading(btn, true, '创建建议单');
  try {
    const payload = {
      asset_symbol: document.getElementById('alpha-symbol').value.trim(),
      underlying_symbol: document.getElementById('alpha-underlying').value.trim(),
      action: 'BUY',
      thesis: document.getElementById('alpha-thesis').value.trim(),
      suggested_quantity: Number(document.getElementById('alpha-qty').value),
      suggested_limit_price: Number(document.getElementById('alpha-limit').value),
      expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(),
    };
    await AlphaAPI.createTicket(payload);
    showToast('建议单已创建', 'success');
    loadAlphaTickets();
    event.target.reset();
  } catch (err) {
    showToast('创建失败: ' + err.message, 'error');
  } finally {
    setButtonLoading(btn, false, '创建建议单');
  }
}

async function loadAlphaWatchlist() {
  const root = document.getElementById('alpha-watchlist');
  if (!root) return;
  try {
    const data = await AlphaAPI.getWatchlist();
    if (!data.items || data.items.length === 0) {
      root.innerHTML = '<span style="color:var(--dim)">暂无观察标的</span>';
      return;
    }
    renderAlphaWatchlist(data.items);
  } catch (err) {
    root.innerHTML = '<span style="color:var(--danger)">加载失败</span>';
  }
}

function renderAlphaWatchlist(items) {
  const root = document.getElementById('alpha-watchlist');
  if (!root) return;
  root.innerHTML = items.map(item => `
    <div class="watchlist-row">
      <strong>${escapeHtml(item.symbol)}</strong>
      <span>${escapeHtml(item.underlying_symbol)}</span>
      <span>优先级: ${item.priority}</span>
    </div>
  `).join('');
}

async function loadAlphaCapabilities() {
  const modeEl = document.getElementById('alpha-execution-mode');
  const reasonEl = document.getElementById('alpha-execution-reason');
  if (!modeEl || !reasonEl) return;
  try {
    const data = await AlphaAPI.getCapabilities();
    renderAlphaExecutionCapability(data);
  } catch (err) {
    modeEl.textContent = '未知';
    reasonEl.textContent = '获取失败';
  }
}

function renderAlphaExecutionCapability(capability) {
  const modeEl = document.getElementById('alpha-execution-mode');
  const reasonEl = document.getElementById('alpha-execution-reason');
  if (modeEl) modeEl.textContent = capability.mode || '未知';
  if (reasonEl) reasonEl.textContent = capability.reason || '';
}

async function runAlphaScan() {
  const root = document.getElementById('alpha-candidates');
  if (!root) return;
  root.innerHTML = '<span class="loading-spinner"></span> 扫描中...';
  try {
    const data = await AlphaAPI.scanResearch();
    if (!data.items || data.items.length === 0) {
      root.innerHTML = '<span style="color:var(--dim)">无候选结果</span>';
      return;
    }
    root.innerHTML = data.items.map(item => `
      <div class="candidate-row">
        <strong>${escapeHtml(item.symbol)}</strong>
        <span>${escapeHtml(item.action)}</span>
        <span>评分: ${formatNumber(item.score, 4)}</span>
        <span>${escapeHtml(item.reason)}</span>
      </div>
    `).join('');
  } catch (err) {
    root.innerHTML = '<span style="color:var(--danger)">扫描失败</span>';
  }
}

async function proposeTopAlphaTicket() {
  try {
    const data = await AlphaAPI.proposeTicket({ thesis_prefix: 'dashboard auto' });
    showToast('建议单已生成: ' + data.asset_symbol, 'success');
    loadAlphaTickets();
  } catch (err) {
    showToast('生成失败: ' + err.message, 'error');
  }
}
