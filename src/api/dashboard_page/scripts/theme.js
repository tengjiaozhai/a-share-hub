// Theme registry
const THEME_IDS = [
  'trading-terminal',
  'mission-control',
  'neutral-modern',
  'hud-signal',
  'mono-grid',
  'openai-editorial',
  'nvidia-power',
  'coinbase-institutional',
];

const THEMES = {
  'trading-terminal': { label: 'Trading Terminal', labelCn: '交易终端', intent: 'dark control room', intentCn: '深色控制室' },
  'mission-control': { label: 'Mission Control', labelCn: '任务控制', intent: 'navy and amber telemetry', intentCn: '海军蓝琥珀遥测' },
  'neutral-modern': { label: 'Neutral Modern', labelCn: '现代中性', intent: 'balanced light reading', intentCn: '平衡浅色阅读' },
  'hud-signal': { label: 'HUD Signal', labelCn: 'HUD信号', intent: 'high-contrast operational dark', intentCn: '高对比度深色' },
  'mono-grid': { label: 'Mono Grid', labelCn: '单色网格', intent: 'terminal-like monochrome', intentCn: '终端单色' },
  'openai-editorial': { label: 'OpenAI Editorial', labelCn: 'OpenAI编辑', intent: 'calm dark editorial', intentCn: '冷静深色编辑' },
  'nvidia-power': { label: 'NVIDIA Power', labelCn: 'NVIDIA性能', intent: 'performance green on black', intentCn: '性能绿黑' },
  'coinbase-institutional': { label: 'Coinbase Institutional', labelCn: 'Coinbase机构', intent: 'clean finance white', intentCn: '干净金融白' },
};

const DEFAULT_THEME = 'trading-terminal';

let _currentTheme = DEFAULT_THEME;

function applyTheme(themeId) {
  if (!THEME_IDS.includes(themeId)) themeId = DEFAULT_THEME;
  _currentTheme = themeId;
  document.documentElement.setAttribute('data-theme', themeId);
  const theme = THEMES[themeId];
  const label = theme ? `${theme.labelCn} ${theme.label}` : themeId;
  const labelEl = document.getElementById('theme-switcher-label');
  if (labelEl) labelEl.textContent = label;
  // Update selected state in menu
  document.querySelectorAll('.theme-menu-item').forEach(item => {
    item.classList.toggle('active', item.dataset.theme === themeId);
  });
}

function getCurrentTheme() {
  return _currentTheme;
}

function initTheme(savedThemeId) {
  applyTheme(savedThemeId || DEFAULT_THEME);
}

function initThemeFromServer(themeId) {
  applyTheme(themeId || DEFAULT_THEME);
}

function openThemeMenu() {
  const menu = document.getElementById('theme-menu');
  const btn = document.getElementById('theme-switcher-btn');
  if (!menu || !btn) return;
  menu.hidden = false;
  btn.setAttribute('aria-expanded', 'true');
  // Render menu items
  renderThemeMenu();
  // Focus selected
  const selected = menu.querySelector('.theme-menu-item.active');
  if (selected) selected.focus();
}

function closeThemeMenu() {
  const menu = document.getElementById('theme-menu');
  const btn = document.getElementById('theme-switcher-btn');
  if (!menu || !btn) return;
  menu.hidden = true;
  btn.setAttribute('aria-expanded', 'false');
  btn.focus();
}

function renderThemeMenu() {
  const menu = document.getElementById('theme-menu');
  if (!menu) return;
  menu.innerHTML = THEME_IDS.map(id => {
    const t = THEMES[id];
    const active = id === _currentTheme ? ' active' : '';
    return `<div class="theme-menu-item${active}" data-theme="${id}" role="menuitem" tabindex="0">
      <span class="theme-swatch" data-theme-preview="${id}"></span>
      <span class="theme-item-label">${t.labelCn} ${t.label}</span>
      <span class="theme-item-intent">${t.intentCn} ${t.intent}</span>
    </div>`;
  }).join('');
  // Bind clicks
  menu.querySelectorAll('.theme-menu-item').forEach(item => {
    item.addEventListener('click', () => {
      applyTheme(item.dataset.theme);
      closeThemeMenu();
      saveThemePreference(item.dataset.theme);
    });
    item.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        applyTheme(item.dataset.theme);
        closeThemeMenu();
        saveThemePreference(item.dataset.theme);
      }
    });
  });
}

function saveThemePreference(themeId) {
  // Merge with existing preferences
  const prefs = {
    watchlist: (document.getElementById('cfg-watchlist')?.value || '').split(',').map(s => s.trim()).filter(Boolean),
    market: document.getElementById('cfg-market')?.value || 'a',
    capital_base: Number(document.getElementById('cfg-capital')?.value || 100) * 10000,
    max_position_ratio: Number(document.getElementById('cfg-max-pos')?.value || 20) / 100,
    stop_loss_ratio: Number(document.getElementById('cfg-stop-loss')?.value || -5) / 100,
    max_daily_loss_ratio: Number(document.getElementById('cfg-max-daily')?.value || -3) / 100,
    execution_mode: typeof execMode !== 'undefined' ? execMode : 'full',
    theme_id: themeId,
  };
  fetch('/api/v1/dashboard/preferences', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(prefs),
  }).catch(() => {});
}

function bindThemeSwitcher() {
  const btn = document.getElementById('theme-switcher-btn');
  const menu = document.getElementById('theme-menu');
  if (!btn || !menu) return;

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (menu.hidden) openThemeMenu();
    else closeThemeMenu();
  });

  // Close on outside click
  document.addEventListener('click', (e) => {
    if (!menu.hidden && !menu.contains(e.target) && e.target !== btn) {
      closeThemeMenu();
    }
  });

  // Close on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !menu.hidden) {
      closeThemeMenu();
    }
  });
}