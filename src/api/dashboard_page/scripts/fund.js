/**
 * 基金行情模块
 * 提供 ETF 实时行情、基金目录、基金净值查询功能
 */

const FundModule = {
  state: {
    initialized: false,
    etfData: [],
    etfRequestToken: 0,
    etfPagination: {
      page: 1,
      pageSize: 20,
      total: 0,
      totalPages: 0,
      query: '',
    },
    catalogFilters: {
      query: '',
      fundType: '',
    },
    catalogData: [],
    catalogRequestToken: 0,
    catalogPagination: {
      page: 1,
      pageSize: 20,
      total: 0,
      totalPages: 0,
    },
    navData: [],
    navRequestToken: 0,
    navRequestKey: '',
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
      this.commitEtfSearch();
      this.resetEtfPagination();
      this.loadEtfSpot();
    });
    document.getElementById('etf-search')?.addEventListener('keyup', (event) => {
      if (event.key === 'Enter') {
        this.commitEtfSearch();
        this.resetEtfPagination();
        this.loadEtfSpot();
      }
    });

    document.getElementById('btn-fund-search')?.addEventListener('click', () => {
      this.commitCatalogFilters();
      this.resetCatalogPagination();
      this.loadFundCatalog();
    });
    document.getElementById('fund-search')?.addEventListener('keyup', (event) => {
      if (event.key === 'Enter') {
        this.commitCatalogFilters();
        this.resetCatalogPagination();
        this.loadFundCatalog();
      }
    });
    document.getElementById('fund-type-filter')?.addEventListener('change', () => {
      this.commitCatalogFilters();
      this.resetCatalogPagination();
      this.loadFundCatalog();
    });

    document.getElementById('btn-query-nav')?.addEventListener('click', () => {
      this.queryFundNav();
    });
    document.getElementById('nav-symbol')?.addEventListener('keyup', (event) => {
      if (event.key === 'Enter') this.queryFundNav();
    });

    document.querySelectorAll('#fund-tabs button').forEach((tab) => {
      tab.addEventListener('click', () => {
        this.switchTab(tab, tab.dataset.target);
      });
    });
  },

  switchTab(tab, target, { skipNavReload = false } = {}) {
    if (!target) return;
    document.querySelectorAll('#fund-tabs button').forEach((button) => {
      button.classList.toggle('active', button === tab);
    });
    document.querySelectorAll('#view-fund .tab-pane').forEach((pane) => {
      pane.classList.toggle('active', `#${pane.id}` === target);
    });
    this.onTabChange(target, { skipNavReload });
  },

  onTabChange(target, { skipNavReload = false } = {}) {
    if (target === '#etf-spot') {
      if (!this.state.etfData.length) this.loadEtfSpot();
      return;
    }
    if (target === '#fund-catalog') {
      if (!this.state.catalogData.length) this.loadFundCatalog();
      return;
    }
    if (target === '#fund-nav' && this.state.currentSymbol && !skipNavReload) {
      this.queryFundNav(this.state.currentSymbol);
    }
  },

  refreshCurrentTab() {
    const activeTab = document.querySelector('#fund-tabs button.active');
    const target = activeTab?.dataset.target || '#etf-spot';
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
    const body = document.getElementById('etf-spot-body');
    const paginationEl = document.getElementById('etf-spot-pagination');
    if (!body) return;

    const requestToken = ++this.state.etfRequestToken;
    body.innerHTML = '<tr><td colspan="11" class="mkt-empty">加载中...</td></tr>';
    if (paginationEl) paginationEl.innerHTML = '';

    try {
      const { page, pageSize, query } = this.state.etfPagination;
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      if (query) params.append('query', query);
      const response = await fetch(`/api/v1/fund/etf/spot?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      if (requestToken !== this.state.etfRequestToken) return;
      this.state.etfData = Array.isArray(data.items) ? data.items : [];
      this.state.etfPagination = {
        page: Number(data.page) || page,
        pageSize: Number(data.page_size) || pageSize,
        total: Number(data.total) || 0,
        totalPages: Number(data.total_pages) || 0,
        query,
      };
      this.updateRefreshTime();
      this.renderEtfTable();
    } catch (error) {
      if (requestToken !== this.state.etfRequestToken) return;
      console.error('加载 ETF 行情失败:', error);
      this.clearEtfState({
        page: this.state.etfPagination.page,
        pageSize: this.state.etfPagination.pageSize,
        query: this.state.etfPagination.query,
      });
      body.innerHTML = '<tr><td colspan="11" class="mkt-empty fund-error">加载失败，请稍后重试</td></tr>';
    }
  },

  renderEtfTable() {
    const body = document.getElementById('etf-spot-body');
    const count = document.getElementById('etf-spot-count');
    const paginationEl = document.getElementById('etf-spot-pagination');
    const data = this.state.etfData;
    const { page, total, totalPages } = this.state.etfPagination;
    if (!body) return;
    if (count) {
      const safePage = totalPages > 0 ? page : 0;
      const safeTotalPages = totalPages > 0 ? totalPages : 0;
      count.textContent = `共 ${total} 只，第 ${safePage} / ${safeTotalPages} 页`;
    }
    if (!data.length) {
      body.innerHTML = '<tr><td colspan="11" class="mkt-empty">暂无数据</td></tr>';
      if (paginationEl) paginationEl.innerHTML = '';
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
    if (!paginationEl) return;
    if (totalPages <= 1) {
      paginationEl.innerHTML = '';
      return;
    }
    paginationEl.innerHTML = `
      <button type="button" onclick="FundModule.goToEtfPage(1)" ${page === 1 ? 'disabled' : ''}>&laquo;</button>
      <button type="button" onclick="FundModule.goToEtfPage(${page - 1})" ${page === 1 ? 'disabled' : ''}>&lsaquo;</button>
      <span class="fund-page-info">${page} / ${totalPages}</span>
      <button type="button" onclick="FundModule.goToEtfPage(${page + 1})" ${page === totalPages ? 'disabled' : ''}>&rsaquo;</button>
      <button type="button" onclick="FundModule.goToEtfPage(${totalPages})" ${page === totalPages ? 'disabled' : ''}>&raquo;</button>
    `;
  },

  clearEtfState({ page = 1, pageSize = this.state.etfPagination.pageSize, query = '' } = {}) {
    this.state.etfData = [];
    this.state.etfPagination = {
      page,
      pageSize,
      total: 0,
      totalPages: 0,
      query,
    };
    const count = document.getElementById('etf-spot-count');
    const paginationEl = document.getElementById('etf-spot-pagination');
    if (count) count.textContent = '共 0 只，第 0 / 0 页';
    if (paginationEl) paginationEl.innerHTML = '';
  },

  resetEtfPagination() {
    this.clearEtfState({ page: 1, query: this.state.etfPagination.query });
  },

  goToEtfPage(page) {
    const totalPages = this.state.etfPagination.totalPages || 1;
    const nextPage = Math.min(Math.max(Number(page) || 1, 1), totalPages);
    if (nextPage === this.state.etfPagination.page) return;
    this.state.etfPagination.page = nextPage;
    this.loadEtfSpot();
    document.getElementById('etf-spot')?.scrollTo({ top: 0, behavior: 'smooth' });
  },

  commitEtfSearch() {
    this.state.etfPagination.query = document.getElementById('etf-search')?.value?.trim() || '';
  },

  async loadFundCatalog() {
    const body = document.getElementById('fund-catalog-body');
    const paginationEl = document.getElementById('fund-catalog-pagination');
    if (!body) return;

    const requestToken = ++this.state.catalogRequestToken;
    body.innerHTML = '<tr><td colspan="5" class="mkt-empty">加载中...</td></tr>';
    if (paginationEl) paginationEl.innerHTML = '';

    try {
      const { page, pageSize } = this.state.catalogPagination;
      const { query, fundType } = this.state.catalogFilters;
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      if (query) params.append('query', query);
      if (fundType) params.append('fund_type', fundType);
      const response = await fetch(`/api/v1/fund/catalog?${params.toString()}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      if (requestToken !== this.state.catalogRequestToken) return;
      this.state.catalogData = Array.isArray(data.items) ? data.items : [];
      this.state.catalogPagination = {
        page: Number(data.page) || page,
        pageSize: Number(data.page_size) || pageSize,
        total: Number(data.total) || 0,
        totalPages: Number(data.total_pages) || 0,
      };
      this.updateRefreshTime();
      this.renderCatalogTable();
    } catch (error) {
      if (requestToken !== this.state.catalogRequestToken) return;
      console.error('加载基金目录失败:', error);
      this.clearCatalogState({
        page: this.state.catalogPagination.page,
        pageSize: this.state.catalogPagination.pageSize,
      });
      body.innerHTML = '<tr><td colspan="5" class="mkt-empty fund-error">加载失败，请稍后重试</td></tr>';
    }
  },

  renderCatalogTable() {
    const body = document.getElementById('fund-catalog-body');
    const count = document.getElementById('fund-catalog-count');
    const paginationEl = document.getElementById('fund-catalog-pagination');
    const data = this.state.catalogData;
    const { page, total, totalPages } = this.state.catalogPagination;
    if (!body) return;
    if (count) count.textContent = `${data.length} / ${total} 只`;
    if (!data.length) {
      body.innerHTML = '<tr><td colspan="5" class="mkt-empty">暂无数据</td></tr>';
      if (paginationEl) paginationEl.innerHTML = '';
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
            <button class="mkt-btn mkt-btn-accent btn-view-nav" type="button" onclick="FundModule.openNavForSymbol('${this.escapeJsString(symbol)}')">
              净值
            </button>
            <button class="mkt-btn mkt-btn-outline btn-view-nav" type="button" onclick="FundModule.addToWatchlist('${this.escapeJsString(symbol)}')">
              加入观察
            </button>
          </td>
        </tr>
      `;
    }).join('');

    if (!paginationEl) return;
    if (totalPages <= 1) {
      paginationEl.innerHTML = '';
      return;
    }
    paginationEl.innerHTML = `
      <button type="button" onclick="FundModule.goToCatalogPage(1)" ${page === 1 ? 'disabled' : ''}>&laquo;</button>
      <button type="button" onclick="FundModule.goToCatalogPage(${page - 1})" ${page === 1 ? 'disabled' : ''}>&lsaquo;</button>
      <span class="fund-page-info">${page} / ${totalPages}</span>
      <button type="button" onclick="FundModule.goToCatalogPage(${page + 1})" ${page === totalPages ? 'disabled' : ''}>&rsaquo;</button>
      <button type="button" onclick="FundModule.goToCatalogPage(${totalPages})" ${page === totalPages ? 'disabled' : ''}>&raquo;</button>
    `;
  },

  clearCatalogState({ page = 1, pageSize = this.state.catalogPagination.pageSize } = {}) {
    this.state.catalogData = [];
    this.state.catalogPagination = {
      page,
      pageSize,
      total: 0,
      totalPages: 0,
    };
    const count = document.getElementById('fund-catalog-count');
    const paginationEl = document.getElementById('fund-catalog-pagination');
    if (count) count.textContent = '0 / 0 只';
    if (paginationEl) paginationEl.innerHTML = '';
  },

  resetCatalogPagination() {
    this.clearCatalogState({ page: 1 });
  },

  commitCatalogFilters() {
    this.state.catalogFilters = {
      query: document.getElementById('fund-search')?.value?.trim() || '',
      fundType: document.getElementById('fund-type-filter')?.value || '',
    };
  },

  goToCatalogPage(page) {
    const totalPages = this.state.catalogPagination.totalPages || 1;
    const nextPage = Math.min(Math.max(Number(page) || 1, 1), totalPages);
    if (nextPage === this.state.catalogPagination.page) return;
    this.state.catalogPagination.page = nextPage;
    this.loadFundCatalog();
    document.getElementById('fund-catalog')?.scrollTo({ top: 0, behavior: 'smooth' });
  },

  openNavForSymbol(symbol) {
    if (!symbol) return;
    const input = document.getElementById('nav-symbol');
    if (input) input.value = symbol;
    const navTab = document.getElementById('fund-nav-tab');
    this.state.currentSymbol = symbol;
    if (navTab) this.switchTab(navTab, '#fund-nav', { skipNavReload: true });
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

    const requestKey = JSON.stringify({ symbol, startDate, endDate });
    const requestToken = ++this.state.navRequestToken;
    this.state.navRequestKey = requestKey;
    body.innerHTML = '<tr><td colspan="6" class="mkt-empty">加载中...</td></tr>';

    try {
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate.replace(/-/g, ''));
      if (endDate) params.append('end_date', endDate.replace(/-/g, ''));
      const query = params.toString();
      const response = await fetch(`/api/v1/fund/nav/${encodeURIComponent(symbol)}${query ? `?${query}` : ''}`);
      const data = await response.json();
      if (requestToken !== this.state.navRequestToken || requestKey !== this.state.navRequestKey) return;
      if (!response.ok) {
        if (response.status === 422 && data?.detail?.code === 'fund_nav_unsupported') {
          this.state.currentSymbol = symbol;
          this.state.navData = [];
          this.updateCurrentSummary(symbol);
          body.innerHTML = '<tr><td colspan="6" class="mkt-empty fund-error">该品种仅支持实时行情/K线，不支持净值查询</td></tr>';
          this.renderNavChart([]);
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }
      this.state.currentSymbol = symbol;
      this.state.navData = Array.isArray(data) ? data : [];
      this.updateCurrentSummary(symbol);
      this.updateRefreshTime();
      this.renderNavTable(this.state.navData);
      try {
        this.renderNavChart(this.state.navData);
      } catch (chartError) {
        console.error('渲染基金净值图表失败:', chartError);
      }
    } catch (error) {
      if (requestToken !== this.state.navRequestToken || requestKey !== this.state.navRequestKey) return;
      console.error('查询基金净值失败:', error);
      this.state.navData = [];
      body.innerHTML = '<tr><td colspan="6" class="mkt-empty fund-error">查询失败，请稍后重试</td></tr>';
      this.renderNavChart([]);
    }
  },

  renderNavTable(data) {
    const body = document.getElementById('fund-nav-body');
    if (!body) return;
    if (!data.length) {
      body.innerHTML = '<tr><td colspan="6" class="mkt-empty">暂无数据</td></tr>';
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

  updateRefreshTime() {
    const el = document.getElementById('fund-last-refresh');
    if (el) el.textContent = `更新于 ${new Date().toLocaleTimeString()}`;
  },

  updateCurrentSummary(symbol) {
    const el = document.getElementById('fund-current-summary');
    if (!el) return;
    const match = this.state.catalogData.find((item) => (
      item.symbol === symbol || item.code === symbol
    ));
    el.textContent = match ? `${match.code || symbol} · ${match.name || '基金'}` : symbol;
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

    if (typeof Chart === 'undefined') {
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

  async addToWatchlist(symbol) {
    if (!symbol) return;
    const match = this.state.catalogData.find((item) => (
      item.symbol === symbol || item.code === symbol
    ));
    try {
      const response = await fetch('/api/v1/fund/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          name: match?.name || symbol,
        }),
      });
      if (response.status === 409) {
        alert(`${symbol} 已在基金观察列表中`);
        return;
      }
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      alert(`已将 ${symbol} 添加到基金观察列表`);
    } catch (error) {
      console.error('添加基金观察失败:', error);
      alert('添加基金观察失败，请稍后重试');
    }
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

  escapeJsString(value) {
    return String(value || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
  },
};
