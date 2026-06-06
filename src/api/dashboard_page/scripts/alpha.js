// Alpha 代币化证券
const ALPHA_ASSETS_API = '/api/v1/alpha/assets';
const ALPHA_TICKETS_API = '/api/v1/alpha/tickets';
const ALPHA_CAPABILITIES_API = '/api/v1/alpha/capabilities';

function renderAlphaExecutionCapability(capability) {
  const modeEl = document.getElementById('alpha-execution-mode');
  const reasonEl = document.getElementById('alpha-execution-reason');
  const dotEl = document.getElementById('alpha-cap-dot');
  modeEl.textContent = capability.mode;
  reasonEl.textContent = capability.reason;
  if (dotEl) {
    const mode = (capability.mode || '').toLowerCase();
    dotEl.className = 'alpha-panel-dot' + (mode === 'auto' || mode === 'enabled' ? ' ok' : mode === 'disabled' ? ' err' : ' warn');
  }
}

function renderAlphaPortfolio(portfolio) {
  const summary = portfolio?.snapshot;
  const positions = portfolio?.positions || [];
  document.getElementById('alpha-portfolio-summary').innerHTML = summary
    ? `NAV: <strong>${escapeHtml(String(summary.nav))}</strong> &nbsp;|&nbsp; Realized: ${escapeHtml(String(summary.realized_pnl))} &nbsp;|&nbsp; Unrealized: ${escapeHtml(String(summary.unrealized_pnl))}`
    : '暂无组合快照';
  document.getElementById('alpha-positions').innerHTML = positions.length
    ? positions.map((item) => `<div class="alpha-position-item"><span class="alpha-position-symbol">${escapeHtml(item.symbol)}</span><span class="alpha-position-detail">${escapeHtml(String(item.quantity))} @ ${escapeHtml(String(item.mark_price))}</span></div>`).join('')
    : '<span style="color:var(--dim)">暂无持仓</span>';
}

function renderAlphaExceptions(exceptions) {
  const root = document.getElementById('alpha-exceptions');
  const dotEl = document.getElementById('alpha-exc-dot');
  const panel = root?.closest('.alpha-panel');
  const isMismatch = exceptions?.latest_status === 'MISMATCH';
  root.innerHTML = isMismatch
    ? '<span style="color:var(--red);font-size:13px">' + escapeHtml(JSON.stringify(exceptions.latest_discrepancies)) + '</span>'
    : '<span style="color:var(--green);font-size:13px">无异常</span>';
  if (dotEl) dotEl.className = 'alpha-panel-dot' + (isMismatch ? ' err' : ' ok');
  if (panel) panel.classList.toggle('alpha-has-exception', isMismatch);
}

function renderAlphaTickets(items) {
  const root = document.getElementById('alpha-tickets');
  const countEl = document.getElementById('alpha-ticket-count');
  if (countEl) countEl.textContent = String(items.length);
  if (!items.length) {
    root.innerHTML = '<div class="alpha-empty-state">暂无建议单</div>';
    return;
  }
  root.innerHTML = items.map((item) => {
    const action = (item.action || 'BUY').toUpperCase();
    const actionClass = action === 'BUY' ? 'buy' : action === 'SELL' ? 'sell' : '';
    const status = (item.status || 'pending').toLowerCase();
    const statusClass = status === 'filled' ? 'filled' : status === 'rejected' ? 'rejected' : 'pending';
    return `<div class="alpha-ticket-item">
      <div>
        <div class="alpha-ticket-symbol">${escapeHtml(item.asset_symbol)}</div>
        <div class="alpha-ticket-underlying">${escapeHtml(item.underlying_symbol || '')}</div>
      </div>
      <span class="alpha-ticket-action ${actionClass}">${escapeHtml(action)}</span>
      <span class="alpha-ticket-qty-price">${escapeHtml(String(item.suggested_quantity))} @ ${escapeHtml(String(item.suggested_limit_price))}</span>
      <span class="alpha-ticket-status ${statusClass}">${escapeHtml(status)}</span>
    </div>`;
  }).join('');
}

async function submitAlphaTicket(event) {
  event.preventDefault();
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
    const response = await fetch(ALPHA_TICKETS_API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error('alpha ticket create failed');
    }
    const workbench = await fetch(WORKBENCH_API).then((res) => res.json());
    renderAlphaTickets(workbench.alpha?.tickets || []);
  } catch (error) {
    console.error('Failed to submit alpha ticket:', error);
    alert('创建建议单失败: ' + error.message);
  }
}

async function loadAlphaAssets() {
  try {
    const res = await fetch(ALPHA_ASSETS_API);
    if (res.ok) {
      const data = await res.json();
      const root = document.getElementById('alpha-assets');
      if (!data.items || data.items.length === 0) {
        root.innerHTML = '<div class="alpha-empty-state">暂无资产</div>';
      } else {
        root.innerHTML = data.items.map(asset => {
          const ms = (asset.market_status || '').toLowerCase();
          const msClass = ms === 'active' || ms === 'open' ? 'active' : ms === 'suspended' || ms === 'halted' ? 'suspended' : 'inactive';
          return `<div class="alpha-asset-item">
            <span class="alpha-asset-symbol">${escapeHtml(asset.symbol)}</span>
            <span class="alpha-asset-underlying">${escapeHtml(asset.underlying_symbol)}</span>
            <span class="alpha-asset-badge ${msClass}">${escapeHtml(asset.market_status || '--')}</span>
            <span class="alpha-asset-badge ${msClass}">${escapeHtml(asset.asset_status || '--')}</span>
          </div>`;
        }).join('');
      }
    }
  } catch (error) {
    console.error('加载Alpha资产失败:', error);
  }
}

async function loadAlphaTickets() {
  try {
    const res = await fetch(WORKBENCH_API);
    if (res.ok) {
      const data = await res.json();
      renderAlphaTickets(data.alpha?.tickets || []);
      renderAlphaPortfolio(data.alpha?.portfolio || {});
      renderAlphaExceptions(data.alpha?.exceptions || {});
      renderAlphaWatchlist(data.alpha?.research?.watchlist || []);
      if (data.alpha?.execution_capability) {
        renderAlphaExecutionCapability(data.alpha.execution_capability);
      }
    }
  } catch (error) {
    console.error('加载Alpha建议单失败:', error);
  }
}

function renderAlphaWatchlist(items) {
  const root = document.getElementById('alpha-watchlist');
  if (!items.length) {
    root.innerHTML = '<div class="alpha-empty-state">暂无观察标的</div>';
    return;
  }
  root.innerHTML = items.map(item => `<div class="alpha-watch-item">
    <span class="alpha-watch-symbol">${escapeHtml(item.symbol)}</span>
    <span class="alpha-watch-underlying">${escapeHtml(item.underlying_symbol)}</span>
    <span class="alpha-watch-priority">P${escapeHtml(String(item.priority))}</span>
  </div>`).join('');
}

async function runAlphaScan() {
  const root = document.getElementById('alpha-candidates');
  root.innerHTML = '<div class="alpha-empty-state" style="color:var(--yellow)">扫描中...</div>';
  try {
    const res = await fetch('/api/v1/alpha/research/scan', { method: 'POST' });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || '扫描失败');
    root.innerHTML = body.items
      .map(item => {
        const action = (item.action || 'hold').toLowerCase();
        const actionClass = action === 'buy' ? 'buy' : action === 'sell' ? 'sell' : 'hold';
        return `<div class="alpha-candidate-item">
          <span class="alpha-candidate-symbol">${escapeHtml(item.symbol)}</span>
          <span class="alpha-candidate-action ${actionClass}">${escapeHtml(item.action)}</span>
          <span class="alpha-candidate-score">${item.score.toFixed(4)}</span>
        </div>`;
      }).join('');
  } catch (error) {
    root.innerHTML = `<div class="alpha-empty-state" style="color:var(--red)">扫描失败: ${escapeHtml(error.message)}</div>`;
  }
}

async function proposeTopAlphaTicket() {
  try {
    const res = await fetch('/api/v1/alpha/research/propose-top-ticket', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thesis_prefix: 'dashboard auto' }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || '生成建议单失败');
    const workbench = await fetch(WORKBENCH_API).then((res) => res.json());
    renderAlphaTickets(workbench.alpha?.tickets || []);
  } catch (error) {
    console.error('生成建议单失败:', error);
    alert('生成建议单失败: ' + error.message);
  }
}
