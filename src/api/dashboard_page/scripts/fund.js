/**
 * 基金行情模块
 * 提供 ETF 实时行情、基金目录、基金净值查询功能
 */

const FundModule = {
  state: {
    initialized: false,
    etfData: [],
    catalogData: [],
    navData: [],
    currentSymbol: '',
    navChart: null,
  },

  init() {
    if (!this.state.initialized) {
      this.bindEvents();
      this.state.initialized = true;
    }
    this.refreshCurrentTab();
    console.log('[Fund] Module initialized');
  },

  bindEvents() {
    document.getElementById('btn-refresh-fund')?.addEventListener('click', () => {
      this.refreshCurrentTab();
    });

    document.getElementById('btn-etf-search')?.addEventListener('click', () => {
      this.filterEtfTable();
    });
    document.getElementById('etf-search')?.addEventListener('keyup', (event) => {
      if (event.key === 'Enter') this.filterEtfTable();
    });
    document.getElementById('etf-limit')?.addEventListener('change', () => {
      this.loadEtfSpot();
    });

    document.getElementById('btn-fund-search')?.addEventListener('click', () => {
      this.loadFundCatalog();
    });
    document.getElementById('fund-search')?.addEventListener('keyup', (event) => {
      if (event.key === 'Enter') this.loadFundCatalog();
    });
    document.getElementById('fund-type-filter')?.addEventListener('change', () => {
      this.loadFundCatalog();
    });
    document.getElementById('fund-limit')?.addEventListener('change', () => {
      this.loadFundCatalog();
    });

    document.getElementById('btn-query-nav')?.addEventListener('click', () => {
      this.queryFundNav();
    });
    document.getElementById('nav-symbol')?.addEventListener('keyup', (event) => {
      if (event.key === 'Enter') this.queryFundNav();
    });

    document.querySelectorAll('#fund-tabs .nav-link').forEach((tab) => {
      tab.addEventListener('shown.bs.tab', (event) => {
        this.onTabChange(event.target.getAttribute('data-bs-target'));
      });
    });
  },

  onTabChange(target) {
    if (target === '#etf-spot') {
      if (!this.state.etfData.length) this.loadEtfSpot();
      return;
    }
    if (target === '#fund-catalog') {
      if (!this.state.catalogData.length) this.loadFundCatalog();
      return;
    }
    if (target === '#fund-nav' && this.state.currentSymbol) {
      this.queryFundNav(this.state.currentSymbol);
    }
  },

  refreshCurrentTab() {
    const activeTab = document.querySelector('#fund-tabs .nav-link.active');
    const target = activeTab?.getAttribute('data-bs-target') || '#etf-spot';
    const btn = document.getElementById('btn-refresh-fund');
    btn?.classList.add('rotating');
    setTimeout(() => btn?.classList.remove('rotating'), 1000);

    if (target === '#fund-catalog') {
      this.loadFundCatalog();
      return;
    }
    if (target === '#fund-nav') {
      if (this.state.currentSymbol || document.getElementById('nav-symbol')?.value?.trim()) {
        this.queryFundNav();
      }
      return;
    }
    this.loadEtfSpot();
  },

  async loadEtfSpot() {
    const limit = document.getElementById('etf-limit')?.value || '50';
    const body = document.getElementById('etf-spot-body');
    if (!body) return;

    body.innerHTML = '<tr><td colspan="11" class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> 加载中...</td></tr>';

    try {
      const response = await fetch(`/api/v1/fund/etf/spot?limit=${encodeURIComponent(limit)}`);
      const data = await response.json();
      this.state.etfData = Array.isArray(data) ? data : [];
      this.renderEtfTable(this.state.etfData);
    } catch (error) {
      console.error('加载 ETF 行情失败:', error);
      body.innerHTML = '<tr><td colspan="11" class="text-center text-danger">加载失败，请稍后重试</td></tr>';
    }
  },

  renderEtfTable(data) {
    const body = document.getElementById('etf-spot-body');
    if (!body) return;
    if (!data.length) {
      body.innerHTML = '<tr><td colspan="11" class="text-center text-muted">暂无数据</td></tr>';
      return;
    }

    body.innerHTML = data.map((item) => `
      <tr>
        <td><span class="fund-code">${item.code || ''}</span></td>
        <td>${item.name || ''}</td>
        <td class="text-end">${this.formatNumber(item.price)}</td>
        <td class="text-end ${this.getChangeClass(item.change_pct)}">${this.formatPercent(item.change_pct)}</td>
        <td class="text-end ${this.getChangeClass(item.change)}">${this.formatNumber(item.change)}</td>
        <td class="text-end">${this.formatVolume(item.volume)}</td>
        <td class="text-end">${this.formatAmount(item.amount)}</td>
        <td class="text-end">${this.formatNumber(item.open)}</td>
        <td class="text-end">${this.formatNumber(item.high)}</td>
        <td class="text-end">${this.formatNumber(item.low)}</td>
        <td class="text-end">${this.formatNumber(item.prev_close)}</td>
      </tr>
    `).join('');
  },

  filterEtfTable() {
    const searchText = document.getElementById('etf-search')?.value?.trim().toLowerCase() || '';
    if (!searchText) {
      this.renderEtfTable(this.state.etfData);
      return;
    }
    const filtered = this.state.etfData.filter((item) => (
      String(item.code || '').toLowerCase().includes(searchText)
      || String(item.name || '').toLowerCase().includes(searchText)
    ));
    this.renderEtfTable(filtered);
  },

  async loadFundCatalog() {
    const query = document.getElementById('fund-search')?.value || '';
    const fundType = document.getElementById('fund-type-filter')?.value || '';
    const limit = document.getElementById('fund-limit')?.value || '50';
    const body = document.getElementById('fund-catalog-body');
    if (!body) return;

    body.innerHTML = '<tr><td colspan="5" class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> 加载中...</td></tr>';

    try {
      const params = new URLSearchParams({ limit });
      if (query) params.append('query', query);
      if (fundType) params.append('fund_type', fundType);
      const response = await fetch(`/api/v1/fund/catalog?${params.toString()}`);
      const data = await response.json();
      this.state.catalogData = Array.isArray(data) ? data : [];
      this.renderCatalogTable(this.state.catalogData);
    } catch (error) {
      console.error('加载基金目录失败:', error);
      body.innerHTML = '<tr><td colspan="5" class="text-center text-danger">加载失败，请稍后重试</td></tr>';
    }
  },

  renderCatalogTable(data) {
    const body = document.getElementById('fund-catalog-body');
    if (!body) return;
    if (!data.length) {
      body.innerHTML = '<tr><td colspan="5" class="text-center text-muted">暂无数据</td></tr>';
      return;
    }

    body.innerHTML = data.map((item) => {
      const symbol = item.symbol || item.code || '';
      return `
        <tr>
          <td><span class="fund-code">${item.code || ''}</span></td>
          <td><span class="fund-name">${item.name || ''}</span></td>
          <td>${item.fund_type || ''}</td>
          <td>${item.exchange || ''}</td>
          <td class="fund-action-cell">
            <button class="btn btn-sm btn-outline-primary btn-view-nav" type="button" onclick="FundModule.openNavForSymbol('${symbol}')">
              净值
            </button>
            <button class="btn btn-sm btn-outline-secondary btn-view-nav" type="button" onclick="FundModule.addToWatchlist('${symbol}')">
              加入观察
            </button>
          </td>
        </tr>
      `;
    }).join('');
  },

  openNavForSymbol(symbol) {
    if (!symbol) return;
    const input = document.getElementById('nav-symbol');
    if (input) input.value = symbol;
    this.state.currentSymbol = symbol;
    const navTab = document.getElementById('fund-nav-tab');
    if (navTab && typeof bootstrap !== 'undefined' && bootstrap.Tab) {
      bootstrap.Tab.getOrCreateInstance(navTab).show();
    }
    this.queryFundNav(symbol);
  },

  async queryFundNav(symbolOverride) {
    const symbol = String(symbolOverride || document.getElementById('nav-symbol')?.value || '').trim();
    if (!symbol) {
      alert('请输入基金代码');
      return;
    }

    const startDate = document.getElementById('nav-start-date')?.value || '';
    const endDate = document.getElementById('nav-end-date')?.value || '';
    const body = document.getElementById('fund-nav-body');
    if (!body) return;

    body.innerHTML = '<tr><td colspan="6" class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> 加载中...</td></tr>';

    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate.replace(/-/g, ''));
      if (endDate) params.append('end_date', endDate.replace(/-/g, ''));
      const query = params.toString();
      const response = await fetch(`/api/v1/fund/nav/${encodeURIComponent(symbol)}${query ? `?${query}` : ''}`);
      const data = await response.json();
      this.state.currentSymbol = symbol;
      this.state.navData = Array.isArray(data) ? data : [];
      this.renderNavTable(this.state.navData);
      this.renderNavChart(this.state.navData);
    } catch (error) {
      console.error('查询基金净值失败:', error);
      body.innerHTML = '<tr><td colspan="6" class="text-center text-danger">查询失败，请稍后重试</td></tr>';
      this.renderNavChart([]);
    }
  },

  renderNavTable(data) {
    const body = document.getElementById('fund-nav-body');
    if (!body) return;
    if (!data.length) {
      body.innerHTML = '<tr><td colspan="6" class="text-center text-muted">暂无数据</td></tr>';
      return;
    }

    body.innerHTML = data.map((item) => `
      <tr>
        <td>${item.date || ''}</td>
        <td class="text-end">${this.formatNumber(item.nav)}</td>
        <td class="text-end">${this.formatNumber(item.acc_nav)}</td>
        <td class="text-end ${this.getChangeClass(item.daily_return)}">${this.formatPercent(item.daily_return)}</td>
        <td>${item.purchase_status || ''}</td>
        <td>${item.redeem_status || ''}</td>
      </tr>
    `).join('');
  },

  renderNavChart(data) {
    const container = document.getElementById('nav-chart-container');
    const canvas = document.getElementById('nav-chart');
    if (!container || !canvas) return;

    if (this.state.navChart) {
      this.state.navChart.destroy();
      this.state.navChart = null;
    }

    if (!data.length) {
      container.style.display = 'none';
      return;
    }

    container.style.display = 'block';
    this.state.navChart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels: data.map((item) => item.date),
        datasets: [{
          label: '单位净值',
          data: data.map((item) => item.nav),
          borderColor: 'rgb(59, 130, 246)',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          tension: 0.1,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
          },
        },
        scales: {
          x: {
            display: true,
            title: {
              display: true,
              text: '日期',
            },
          },
          y: {
            display: true,
            title: {
              display: true,
              text: '净值',
            },
          },
        },
      },
    });
  },

  addToWatchlist(symbol) {
    if (!symbol) return;
    if (typeof addToWorkspaceWatchlist === 'function') {
      addToWorkspaceWatchlist(symbol);
      return;
    }
    const watchlistInput = document.getElementById('cfg-watchlist');
    if (!watchlistInput) return;
    const current = watchlistInput.value.split(',').map((item) => item.trim()).filter(Boolean);
    if (current.includes(symbol)) {
      alert(`${symbol} 已在观察列表中`);
      return;
    }
    current.push(symbol);
    watchlistInput.value = current.join(', ');
    alert(`已将 ${symbol} 添加到观察列表`);
  },

  formatNumber(value) {
    if (value === null || value === undefined || value === '') return '-';
    return Number(value).toFixed(2);
  },

  formatPercent(value) {
    if (value === null || value === undefined || value === '') return '-';
    const num = Number(value);
    return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
  },

  formatVolume(value) {
    if (value === null || value === undefined || value === '') return '-';
    const num = Number(value);
    if (num >= 100000000) return `${(num / 100000000).toFixed(2)}亿`;
    if (num >= 10000) return `${(num / 10000).toFixed(2)}万`;
    return num.toLocaleString('zh-CN');
  },

  formatAmount(value) {
    if (value === null || value === undefined || value === '') return '-';
    const num = Number(value);
    if (num >= 100000000) return `${(num / 100000000).toFixed(2)}亿`;
    if (num >= 10000) return `${(num / 10000).toFixed(2)}万`;
    return num.toLocaleString('zh-CN');
  },

  getChangeClass(value) {
    if (value === null || value === undefined || value === '') return '';
    const num = Number(value);
    if (num > 0) return 'change-positive';
    if (num < 0) return 'change-negative';
    return 'change-zero';
  },
};
