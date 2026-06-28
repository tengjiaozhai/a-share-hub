/**
 * 基金视图模块
 * 提供 ETF 实时行情、基金目录、基金净值查询功能
 */

// 基金模块状态
const FundModule = {
  state: {
    etfData: [],
    catalogData: [],
    navData: [],
    currentSymbol: '',
    isLoading: false,
  },

  // 初始化模块
  init() {
    this.bindEvents();
    this.loadEtfSpot();
    console.log('[Fund] Module initialized');
  },

  // 绑定事件
  bindEvents() {
    // 刷新按钮
    document.getElementById('btn-refresh-fund')?.addEventListener('click', () => {
      this.refreshCurrentTab();
    });

    // ETF 搜索
    document.getElementById('btn-etf-search')?.addEventListener('click', () => {
      this.filterEtfTable();
    });
    document.getElementById('etf-search')?.addEventListener('keyup', (e) => {
      if (e.key === 'Enter') this.filterEtfTable();
    });
    document.getElementById('etf-limit')?.addEventListener('change', () => {
      this.loadEtfSpot();
    });

    // 基金目录搜索
    document.getElementById('btn-fund-search')?.addEventListener('click', () => {
      this.loadFundCatalog();
    });
    document.getElementById('fund-search')?.addEventListener('keyup', (e) => {
      if (e.key === 'Enter') this.loadFundCatalog();
    });
    document.getElementById('fund-type-filter')?.addEventListener('change', () => {
      this.loadFundCatalog();
    });
    document.getElementById('fund-limit')?.addEventListener('change', () => {
      this.loadFundCatalog();
    });

    // 基金净值查询
    document.getElementById('btn-query-nav')?.addEventListener('click', () => {
      this.queryFundNav();
    });
    document.getElementById('nav-symbol')?.addEventListener('keyup', (e) => {
      if (e.key === 'Enter') this.queryFundNav();
    });

    // 标签页切换
    document.querySelectorAll('#fund-tabs .nav-link').forEach(tab => {
      tab.addEventListener('shown.bs.tab', (e) => {
        const target = e.target.getAttribute('data-bs-target');
        this.onTabChange(target);
      });
    });
  },

  // 标签页切换处理
  onTabChange(target) {
    switch (target) {
      case '#etf-spot':
        if (this.state.etfData.length === 0) this.loadEtfSpot();
        break;
      case '#fund-catalog':
        if (this.state.catalogData.length === 0) this.loadFundCatalog();
        break;
      case '#fund-nav':
        // 净值查询需要用户主动触发
        break;
    }
  },

  // 刷新当前标签页
  refreshCurrentTab() {
    const activeTab = document.querySelector('#fund-tabs .nav-link.active');
    const target = activeTab?.getAttribute('data-bs-target');
    
    const btn = document.getElementById('btn-refresh-fund');
    btn?.classList.add('rotating');
    setTimeout(() => btn?.classList.remove('rotating'), 1000);

    switch (target) {
      case '#etf-spot':
        this.loadEtfSpot();
        break;
      case '#fund-catalog':
        this.loadFundCatalog();
        break;
      case '#fund-nav':
        this.queryFundNav();
        break;
    }
  },

  // 加载 ETF 实时行情
  async loadEtfSpot() {
    const limit = document.getElementById('etf-limit')?.value || 50;
    const tbody = document.getElementById('etf-spot-body');
    
    this.showLoading(tbody, '正在加载 ETF 行情...');
    
    try {
      const response = await fetch(`/api/v1/fund/etf/spot?limit=${limit}`, {
        headers: this.getHeaders()
      });
      
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      this.state.etfData = await response.json();
      this.renderEtfTable(this.state.etfData);
    } catch (error) {
      console.error('[Fund] Error loading ETF spot:', error);
      this.showError(tbody, '加载 ETF 行情失败: ' + error.message);
    }
  },

  // 渲染 ETF 表格
  renderEtfTable(data) {
    const tbody = document.getElementById('etf-spot-body');
    if (!data || data.length === 0) {
      this.showEmpty(tbody, '暂无 ETF 数据');
      return;
    }

    tbody.innerHTML = data.map(etf => `
      <tr>
        <td><span class="fund-code">${etf.code || '-'}</span></td>
        <td><span class="fund-name" title="${etf.name || ''}">${etf.name || '-'}</span></td>
        <td class="text-end">${this.formatPrice(etf.price)}</td>
        <td class="text-end ${this.getChangeClass(etf.change_pct)}">
          ${this.formatPercent(etf.change_pct)}
        </td>
        <td class="text-end ${this.getChangeClass(etf.change)}">
          ${this.formatChange(etf.change)}
        </td>
        <td class="text-end">${this.formatVolume(etf.volume)}</td>
        <td class="text-end">${this.formatAmount(etf.amount)}</td>
        <td class="text-end">${this.formatPrice(etf.open)}</td>
        <td class="text-end">${this.formatPrice(etf.high)}</td>
        <td class="text-end">${this.formatPrice(etf.low)}</td>
        <td class="text-end">${this.formatPrice(etf.prev_close)}</td>
      </tr>
    `).join('');
  },

  // 过滤 ETF 表格
  filterEtfTable() {
    const search = document.getElementById('etf-search')?.value.toLowerCase() || '';
    if (!search) {
      this.renderEtfTable(this.state.etfData);
      return;
    }

    const filtered = this.state.etfData.filter(etf => 
      (etf.code && etf.code.includes(search)) ||
      (etf.name && etf.name.toLowerCase().includes(search))
    );
    this.renderEtfTable(filtered);
  },

  // 加载基金目录
  async loadFundCatalog() {
    const query = document.getElementById('fund-search')?.value || '';
    const fundType = document.getElementById('fund-type-filter')?.value || '';
    const limit = document.getElementById('fund-limit')?.value || 50;
    const tbody = document.getElementById('fund-catalog-body');
    
    this.showLoading(tbody, '正在加载基金目录...');
    
    try {
      const params = new URLSearchParams({ limit });
      if (query) params.set('query', query);
      if (fundType) params.set('fund_type', fundType);
      
      const response = await fetch(`/api/v1/fund/catalog?${params}`, {
        headers: this.getHeaders()
      });
      
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      this.state.catalogData = await response.json();
      this.renderCatalogTable(this.state.catalogData);
    } catch (error) {
      console.error('[Fund] Error loading fund catalog:', error);
      this.showError(tbody, '加载基金目录失败: ' + error.message);
    }
  },

  // 渲染基金目录表格
  renderCatalogTable(data) {
    const tbody = document.getElementById('fund-catalog-body');
    if (!data || data.length === 0) {
      this.showEmpty(tbody, '暂无基金数据');
      return;
    }

    tbody.innerHTML = data.map(fund => `
      <tr>
        <td><span class="fund-code">${fund.code || '-'}</span></td>
        <td><span class="fund-name" title="${fund.name || ''}">${fund.name || '-'}</span></td>
        <td><span class="fund-type-badge">${fund.fund_type || '-'}</span></td>
        <td>${fund.exchange || '-'}</td>
        <td>
          <button class="btn btn-sm btn-outline-primary btn-view-nav" 
                  onclick="FundModule.viewFundNav('${fund.code}')"
                  title="查看净值">
            <i class="bi bi-graph-up"></i> 净值
          </button>
        </td>
      </tr>
    `).join('');
  },

  // 查看基金净值
  viewFundNav(symbol) {
    // 切换到净值标签页
    const navTab = document.getElementById('fund-nav-tab');
    if (navTab) {
      const tab = new bootstrap.Tab(navTab);
      tab.show();
    }
    
    // 设置代码并查询
    const input = document.getElementById('nav-symbol');
    if (input) {
      input.value = symbol;
      this.queryFundNav();
    }
  },

  // 查询基金净值
  async queryFundNav() {
    const symbol = document.getElementById('nav-symbol')?.value.trim();
    if (!symbol) {
      alert('请输入基金代码');
      return;
    }

    const startDate = document.getElementById('nav-start-date')?.value || '';
    const endDate = document.getElementById('nav-end-date')?.value || '';
    const tbody = document.getElementById('fund-nav-body');
    
    this.state.currentSymbol = symbol;
    this.showLoading(tbody, `正在查询 ${symbol} 的净值数据...`);
    
    try {
      const params = new URLSearchParams();
      if (startDate) params.set('start_date', startDate.replace(/-/g, ''));
      if (endDate) params.set('end_date', endDate.replace(/-/g, ''));
      
      const response = await fetch(`/api/v1/fund/nav/${symbol}?${params}`, {
        headers: this.getHeaders()
      });
      
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      this.state.navData = await response.json();
      this.renderNavTable(this.state.navData);
      this.renderNavChart(this.state.navData);
    } catch (error) {
      console.error('[Fund] Error querying fund NAV:', error);
      this.showError(tbody, '查询基金净值失败: ' + error.message);
    }
  },

  // 渲染净值表格
  renderNavTable(data) {
    const tbody = document.getElementById('fund-nav-body');
    if (!data || data.length === 0) {
      this.showEmpty(tbody, '暂无净值数据');
      return;
    }

    tbody.innerHTML = data.map(nav => `
      <tr>
        <td>${nav.date || '-'}</td>
        <td class="text-end">${this.formatNav(nav.nav)}</td>
        <td class="text-end">${this.formatNav(nav.acc_nav)}</td>
        <td class="text-end ${this.getChangeClass(nav.change_pct)}">
          ${this.formatPercent(nav.change_pct)}
        </td>
        <td>${nav.purchase_status || '-'}</td>
        <td>${nav.redeem_status || '-'}</td>
      </tr>
    `).join('');
  },

  // 渲染净值图表
  renderNavChart(data) {
    const container = document.getElementById('nav-chart-container');
    const canvas = document.getElementById('nav-chart');
    
    if (!data || data.length === 0) {
      container.style.display = 'none';
      return;
    }

    container.style.display = 'block';
    
    // 如果已有图表，先销毁
    if (this.navChart) {
      this.navChart.destroy();
    }

    // 准备图表数据
    const labels = data.map(d => d.date).reverse();
    const navValues = data.map(d => d.nav).reverse();
    
    // 创建图表
    const ctx = canvas.getContext('2d');
    this.navChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: `${this.state.currentSymbol} 单位净值`,
          data: navValues,
          borderColor: getComputedStyle(document.documentElement).getPropertyValue('--primary-color').trim() || '#0d6efd',
          backgroundColor: 'transparent',
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          tension: 0.1,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: true,
            position: 'top',
          },
          tooltip: {
            mode: 'index',
            intersect: false,
            callbacks: {
              label: function(context) {
                return `净值: ${context.parsed.y.toFixed(4)}`;
              }
            }
          }
        },
        scales: {
          x: {
            display: true,
            grid: {
              display: false,
            },
            ticks: {
              maxTicksLimit: 10,
            }
          },
          y: {
            display: true,
            grid: {
              color: 'rgba(0,0,0,0.1)',
            },
            ticks: {
              callback: function(value) {
                return value.toFixed(4);
              }
            }
          }
        },
        interaction: {
          mode: 'nearest',
          axis: 'x',
          intersect: false,
        }
      }
    });
  },

  // 工具方法
  getHeaders() {
    const headers = { 'Content-Type': 'application/json' };
    // 如果有认证 token，添加到 headers
    const token = localStorage.getItem('auth_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  },

  showLoading(tbody, message) {
    tbody.innerHTML = `
      <tr>
        <td colspan="${tbody.closest('table')?.querySelectorAll('th').length || 11}" 
            class="text-center text-muted">
          <div class="spinner-border spinner-border-sm" role="status">
            <span class="visually-hidden">加载中...</span>
          </div>
          ${message}
        </td>
      </tr>
    `;
  },

  showError(tbody, message) {
    tbody.innerHTML = `
      <tr>
        <td colspan="${tbody.closest('table')?.querySelectorAll('th').length || 11}" 
            class="text-center text-danger">
          <i class="bi bi-exclamation-circle"></i> ${message}
        </td>
      </tr>
    `;
  },

  showEmpty(tbody, message) {
    tbody.innerHTML = `
      <tr>
        <td colspan="${tbody.closest('table')?.querySelectorAll('th').length || 11}" 
            class="text-center text-muted">
          <i class="bi bi-inbox"></i> ${message}
        </td>
      </tr>
    `;
  },

  formatPrice(value) {
    if (value === null || value === undefined || isNaN(value)) return '-';
    return Number(value).toFixed(3);
  },

  formatNav(value) {
    if (value === null || value === undefined || isNaN(value)) return '-';
    return Number(value).toFixed(4);
  },

  formatPercent(value) {
    if (value === null || value === undefined || isNaN(value)) return '-';
    const sign = value > 0 ? '+' : '';
    return `${sign}${Number(value).toFixed(2)}%`;
  },

  formatChange(value) {
    if (value === null || value === undefined || isNaN(value)) return '-';
    const sign = value > 0 ? '+' : '';
    return `${sign}${Number(value).toFixed(3)}`;
  },

  formatVolume(value) {
    if (value === null || value === undefined || isNaN(value)) return '-';
    if (value >= 100000000) {
      return (value / 100000000).toFixed(2) + '亿';
    } else if (value >= 10000) {
      return (value / 10000).toFixed(2) + '万';
    }
    return value.toLocaleString();
  },

  formatAmount(value) {
    if (value === null || value === undefined || isNaN(value)) return '-';
    if (value >= 100000000) {
      return (value / 100000000).toFixed(2) + '亿';
    } else if (value >= 10000) {
      return (value / 10000).toFixed(2) + '万';
    }
    return value.toLocaleString();
  },

  getChangeClass(value) {
    if (value === null || value === undefined || isNaN(value)) return 'change-zero';
    if (value > 0) return 'change-positive';
    if (value < 0) return 'change-negative';
    return 'change-zero';
  },
};

// 导出模块
window.FundModule = FundModule;
