/**
 * 基金视图模块
 * 提供 ETF 实时行情、基金目录、基金净值查询、基金分析、基金对比、基金筛选功能
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

    // 基金分析
    document.getElementById('btn-query-analysis')?.addEventListener('click', () => {
      const symbol = document.getElementById('analysis-symbol')?.value?.trim();
      if (symbol) this.loadFundAnalysis(symbol);
    });
    document.getElementById('analysis-symbol')?.addEventListener('keyup', (e) => {
      if (e.key === 'Enter') {
        const symbol = e.target.value?.trim();
        if (symbol) this.loadFundAnalysis(symbol);
      }
    });

    // 基金对比
    document.getElementById('btn-compare-funds')?.addEventListener('click', () => {
      const symbolsStr = document.getElementById('compare-symbols')?.value?.trim();
      if (symbolsStr) {
        const symbols = symbolsStr.split(',').map(s => s.trim()).filter(s => s);
        this.compareFunds(symbols);
      }
    });
    document.getElementById('compare-symbols')?.addEventListener('keyup', (e) => {
      if (e.key === 'Enter') {
        const symbolsStr = e.target.value?.trim();
        if (symbolsStr) {
          const symbols = symbolsStr.split(',').map(s => s.trim()).filter(s => s);
          this.compareFunds(symbols);
        }
      }
    });

    // 基金筛选
    document.getElementById('btn-screen-funds')?.addEventListener('click', () => {
      const filters = {
        fund_type: document.getElementById('screen-fund-type')?.value || '',
        min_return_1y: document.getElementById('screen-min-return')?.value || '',
        max_drawdown: document.getElementById('screen-max-drawdown')?.value || '',
        min_sharpe: document.getElementById('screen-min-sharpe')?.value || '',
        limit: document.getElementById('screen-limit')?.value || '20',
      };
      this.screenFunds(filters);
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
      case '#fund-analysis':
        // 基金分析需要用户主动触发
        break;
      case '#fund-compare':
        // 基金对比需要用户主动触发
        break;
      case '#fund-screen':
        // 基金筛选需要用户主动触发
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
      case '#fund-analysis':
        const analysisSymbol = document.getElementById('analysis-symbol')?.value?.trim();
        if (analysisSymbol) this.loadFundAnalysis(analysisSymbol);
        break;
      case '#fund-compare':
        const compareSymbolsStr = document.getElementById('compare-symbols')?.value?.trim();
        if (compareSymbolsStr) {
          const symbols = compareSymbolsStr.split(',').map(s => s.trim()).filter(s => s);
          this.compareFunds(symbols);
        }
        break;
      case '#fund-screen':
        const filters = {
          fund_type: document.getElementById('screen-fund-type')?.value || '',
          min_return_1y: document.getElementById('screen-min-return')?.value || '',
          max_drawdown: document.getElementById('screen-max-drawdown')?.value || '',
          min_sharpe: document.getElementById('screen-min-sharpe')?.value || '',
          limit: document.getElementById('screen-limit')?.value || '20',
        };
        this.screenFunds(filters);
        break;
    }
  },

  // 加载 ETF 实时行情
  async loadEtfSpot() {
    const limit = document.getElementById('etf-limit')?.value || 50;
    const body = document.getElementById('etf-spot-body');
    if (!body) return;
    
    body.innerHTML = '<tr><td colspan="11" class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> 加载中...</td></tr>';
    
    try {
      const response = await fetch(`/api/v1/fund/etf/spot?limit=${limit}`);
      const data = await response.json();
      
      this.state.etfData = data;
      this.renderEtfTable(data);
    } catch (error) {
      console.error('加载 ETF 行情失败:', error);
      body.innerHTML = '<tr><td colspan="11" class="text-center text-danger">加载失败，请稍后重试</td></tr>';
    }
  },

  // 渲染 ETF 表格
  renderEtfTable(data) {
    const body = document.getElementById('etf-spot-body');
    if (!body) return;
    
    if (!data || data.length === 0) {
      body.innerHTML = '<tr><td colspan="11" class="text-center text-muted">暂无数据</td></tr>';
      return;
    }
    
    body.innerHTML = data.map(item => `
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

  // 过滤 ETF 表格
  filterEtfTable() {
    const searchText = document.getElementById('etf-search')?.value?.toLowerCase() || '';
    if (!searchText) {
      this.renderEtfTable(this.state.etfData);
      return;
    }
    
    const filtered = this.state.etfData.filter(item => 
      (item.code && item.code.toLowerCase().includes(searchText)) ||
      (item.name && item.name.toLowerCase().includes(searchText))
    );
    this.renderEtfTable(filtered);
  },

  // 加载基金目录
  async loadFundCatalog() {
    const query = document.getElementById('fund-search')?.value || '';
    const fundType = document.getElementById('fund-type-filter')?.value || '';
    const limit = document.getElementById('fund-limit')?.value || 50;
    const body = document.getElementById('fund-catalog-body');
    if (!body) return;
    
    body.innerHTML = '<tr><td colspan="5" class="text-center"><div class="spinner-border spinner-border-sm" role="status"></div> 加载中...</td></tr>';
    
    try {
      const params = new URLSearchParams({ limit });
      if (query) params.append('query', query);
      if (fundType) params.append('fund_type', fundType);
      
      const response = await fetch(`/api/v1/fund/catalog?${params}`);
      const data = await response.json();
      
      this.state.catalogData = data;
      this.renderCatalogTable(data);
    } catch (error) {
      console.error('加载基金目录失败:', error);
      body.innerHTML = '<tr><td colspan="5" class="text-center text-danger">加载失败，请稍后重试</td></tr>';
    }
  },

  // 渲染基金目录表格
  renderCatalogTable(data) {
    const body = document.getElementById('fund-catalog-body');
    if (!body) return;
    
    if (!data || data.length === 0) {
      body.innerHTML = '<tr><td colspan="5" class="text-center text-muted">暂无数据</td></tr>';
      return;
    }
    
    body.innerHTML = data.map(item => `
      <tr>
        <td><span class="fund-code">${item.code || ''}</span></td>
        <td>${item.name || ''}</td>
        <td>${item.fund_type || ''}</td>
        <td>${item.exchange || ''}</td>
        <td>
          <button class="btn btn-sm btn-outline-primary" onclick="FundModule.loadFundAnalysis('${item.symbol}')">
            分析
          </button>
          <button class="btn btn-sm btn-outline-secondary" onclick="FundModule.addToWatchlist('${item.symbol}')">
            加入观察
          </button>
        </td>
      </tr>
    `).join('');
  },

  // 查询基金净值
  async queryFundNav() {
    const symbol = document.getElementById('nav-symbol')?.value?.trim();
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
      
      const response = await fetch(`/api/v1/fund/nav/${symbol}?${params}`);
      const data = await response.json();
      
      this.state.navData = data;
      this.state.currentSymbol = symbol;
      this.renderNavTable(data);
      this.renderNavChart(data);
    } catch (error) {
      console.error('查询基金净值失败:', error);
      body.innerHTML = '<tr><td colspan="6" class="text-center text-danger">查询失败，请稍后重试</td></tr>';
    }
  },

  // 渲染净值表格
  renderNavTable(data) {
    const body = document.getElementById('fund-nav-body');
    if (!body) return;
    
    if (!data || data.length === 0) {
      body.innerHTML = '<tr><td colspan="6" class="text-center text-muted">暂无数据</td></tr>';
      return;
    }
    
    body.innerHTML = data.map(item => `
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

  // 渲染净值图表
  renderNavChart(data) {
    const container = document.getElementById('nav-chart-container');
    const canvas = document.getElementById('nav-chart');
    if (!container || !canvas || !data || data.length === 0) {
      if (container) container.style.display = 'none';
      return;
    }
    
    container.style.display = 'block';
    
    const ctx = canvas.getContext('2d');
    const labels = data.map(item => item.date);
    const navData = data.map(item => item.nav);
    
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: '单位净值',
          data: navData,
          borderColor: 'rgb(59, 130, 246)',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          tension: 0.1,
          fill: true,
        }]
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
              text: '日期'
            }
          },
          y: {
            display: true,
            title: {
              display: true,
              text: '净值'
            }
          }
        }
      }
    });
  },

  // 添加到观察列表
  addToWatchlist(symbol) {
    const watchlistInput = document.getElementById('cfg-watchlist');
    if (!watchlistInput) return;
    
    const current = watchlistInput.value || '';
    const symbols = current.split(',').map(s => s.trim()).filter(s => s);
    
    if (!symbols.includes(symbol)) {
      symbols.push(symbol);
      watchlistInput.value = symbols.join(', ');
      alert(`已将 ${symbol} 添加到观察列表`);
    } else {
      alert(`${symbol} 已在观察列表中`);
    }
  },

  // 格式化数字
  formatNumber(value) {
    if (value === null || value === undefined) return '-';
    return Number(value).toFixed(2);
  },

  // 格式化百分比
  formatPercent(value) {
    if (value === null || value === undefined) return '-';
    const num = Number(value);
    return (num >= 0 ? '+' : '') + num.toFixed(2) + '%';
  },

  // 格式化成交量
  formatVolume(value) {
    if (value === null || value === undefined) return '-';
    const num = Number(value);
    if (num >= 100000000) {
      return (num / 100000000).toFixed(2) + '亿';
    } else if (num >= 10000) {
      return (num / 10000).toFixed(2) + '万';
    }
    return num.toLocaleString();
  },

  // 格式化成交额
  formatAmount(value) {
    if (value === null || value === undefined) return '-';
    const num = Number(value);
    if (num >= 100000000) {
      return (num / 100000000).toFixed(2) + '亿';
    } else if (num >= 10000) {
      return (num / 10000).toFixed(2) + '万';
    }
    return num.toLocaleString();
  },

  // 获取涨跌样式类
  getChangeClass(value) {
    if (value === null || value === undefined) return '';
    const num = Number(value);
    if (num > 0) return 'change-positive';
    if (num < 0) return 'change-negative';
    return 'change-zero';
  },

  // 加载基金分析
  async loadFundAnalysis(symbol) {
    if (!symbol) return;
    
    // 切换到基金分析标签页
    const analysisTab = document.getElementById('fund-analysis-tab');
    if (analysisTab) {
      const tab = new bootstrap.Tab(analysisTab);
      tab.show();
    }
    
    // 设置输入框值
    const input = document.getElementById('analysis-symbol');
    if (input) input.value = symbol;
    
    const resultContainer = document.getElementById('fund-analysis-result');
    if (!resultContainer) return;
    
    resultContainer.innerHTML = '<div class="fund-loading"><div class="spinner-border" role="status"></div><p>正在分析基金...</p></div>';
    
    try {
      const response = await fetch(`/api/v1/fund/analysis/performance/${symbol}`);
      const data = await response.json();
      
      if (data.error) {
        resultContainer.innerHTML = `<div class="fund-analysis-empty"><i class="bi bi-exclamation-circle"></i><p>${data.error}</p></div>`;
        return;
      }
      
      // 获取评级
      const ratingResponse = await fetch(`/api/v1/fund/analysis/rating/${symbol}`);
      const ratingData = await ratingResponse.json();
      
      this.renderFundAnalysis(data, ratingData);
    } catch (error) {
      console.error('加载基金分析失败:', error);
      resultContainer.innerHTML = '<div class="fund-analysis-empty"><i class="bi bi-exclamation-circle"></i><p>加载基金分析失败，请稍后重试</p></div>';
    }
  },

  // 渲染基金分析结果
  renderFundAnalysis(data, ratingData) {
    const resultContainer = document.getElementById('fund-analysis-result');
    if (!resultContainer) return;
    
    const ratingClass = ratingData.rating?.toLowerCase() || 'a';
    const returns = data.returns || {};
    const riskMetrics = data.risk_metrics || {};
    
    resultContainer.innerHTML = `
      <div class="fund-analysis-card">
        <div class="fund-analysis-header">
          <div>
            <h3>${data.symbol} 基金分析</h3>
            <p class="text-muted mb-0">最新净值: ${data.latest_nav} (${data.latest_date})</p>
          </div>
          <div class="fund-rating-badge ${ratingClass}">
            ${ratingData.rating || 'N/A'}
          </div>
        </div>
        
        <div class="fund-metrics-grid">
          <div class="fund-metric-item">
            <div class="fund-metric-label">近1月收益</div>
            <div class="fund-metric-value ${returns['1m'] >= 0 ? 'positive' : 'negative'}">
              ${returns['1m'] >= 0 ? '+' : ''}${returns['1m']}%
            </div>
          </div>
          <div class="fund-metric-item">
            <div class="fund-metric-label">近3月收益</div>
            <div class="fund-metric-value ${returns['3m'] >= 0 ? 'positive' : 'negative'}">
              ${returns['3m'] >= 0 ? '+' : ''}${returns['3m']}%
            </div>
          </div>
          <div class="fund-metric-item">
            <div class="fund-metric-label">近6月收益</div>
            <div class="fund-metric-value ${returns['6m'] >= 0 ? 'positive' : 'negative'}">
              ${returns['6m'] >= 0 ? '+' : ''}${returns['6m']}%
            </div>
          </div>
          <div class="fund-metric-item">
            <div class="fund-metric-label">近1年收益</div>
            <div class="fund-metric-value ${returns['1y'] >= 0 ? 'positive' : 'negative'}">
              ${returns['1y'] >= 0 ? '+' : ''}${returns['1y']}%
            </div>
          </div>
          <div class="fund-metric-item">
            <div class="fund-metric-label">年化收益率</div>
            <div class="fund-metric-value ${returns['annualized'] >= 0 ? 'positive' : 'negative'}">
              ${returns['annualized'] >= 0 ? '+' : ''}${returns['annualized']}%
            </div>
          </div>
          <div class="fund-metric-item">
            <div class="fund-metric-label">最大回撤</div>
            <div class="fund-metric-value negative">
              ${riskMetrics['max_drawdown']}%
            </div>
          </div>
          <div class="fund-metric-item">
            <div class="fund-metric-label">波动率</div>
            <div class="fund-metric-value">
              ${riskMetrics['volatility']}%
            </div>
          </div>
          <div class="fund-metric-item">
            <div class="fund-metric-label">夏普比率</div>
            <div class="fund-metric-value">
              ${riskMetrics['sharpe_ratio']}
            </div>
          </div>
        </div>
        
        <div class="fund-chart-container">
          <canvas id="fund-analysis-chart"></canvas>
        </div>
      </div>
    `;
    
    // 绘制净值走势图
    if (data.nav_history && data.nav_history.length > 0) {
      this.drawFundAnalysisChart(data.nav_history);
    }
  },

  // 绘制基金分析图表
  drawFundAnalysisChart(navHistory) {
    const ctx = document.getElementById('fund-analysis-chart')?.getContext('2d');
    if (!ctx) return;
    
    const labels = navHistory.map(item => item.date);
    const navData = navHistory.map(item => item.nav);
    
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: '单位净值',
          data: navData,
          borderColor: 'rgb(59, 130, 246)',
          backgroundColor: 'rgba(59, 130, 246, 0.1)',
          tension: 0.1,
          fill: true,
        }]
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
              text: '日期'
            }
          },
          y: {
            display: true,
            title: {
              display: true,
              text: '净值'
            }
          }
        }
      }
    });
  },

  // 基金对比
  async compareFunds(symbols) {
    if (!symbols || symbols.length < 2) {
      alert('请输入至少两个基金代码进行对比');
      return;
    }
    
    const resultContainer = document.getElementById('fund-compare-result');
    if (!resultContainer) return;
    
    resultContainer.innerHTML = '<div class="fund-loading"><div class="spinner-border" role="status"></div><p>正在对比基金...</p></div>';
    
    try {
      const response = await fetch('/api/v1/fund/analysis/compare', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(symbols),
      });
      const data = await response.json();
      
      if (data.error) {
        resultContainer.innerHTML = `<div class="fund-compare-empty"><i class="bi bi-exclamation-circle"></i><p>${data.error}</p></div>`;
        return;
      }
      
      this.renderFundComparison(data);
    } catch (error) {
      console.error('基金对比失败:', error);
      resultContainer.innerHTML = '<div class="fund-compare-empty"><i class="bi bi-exclamation-circle"></i><p>基金对比失败，请稍后重试</p></div>';
    }
  },

  // 渲染基金对比结果
  renderFundComparison(data) {
    const resultContainer = document.getElementById('fund-compare-result');
    if (!resultContainer) return;
    
    const funds = data.funds || [];
    const summary = data.summary || {};
    
    let tableRows = funds.map(fund => `
      <tr>
        <td><strong>${fund.symbol}</strong></td>
        <td>${fund.latest_nav}</td>
        <td class="${fund.returns['1m'] >= 0 ? 'text-success' : 'text-danger'}">
          ${fund.returns['1m'] >= 0 ? '+' : ''}${fund.returns['1m']}%
        </td>
        <td class="${fund.returns['3m'] >= 0 ? 'text-success' : 'text-danger'}">
          ${fund.returns['3m'] >= 0 ? '+' : ''}${fund.returns['3m']}%
        </td>
        <td class="${fund.returns['1y'] >= 0 ? 'text-success' : 'text-danger'}">
          ${fund.returns['1y'] >= 0 ? '+' : ''}${fund.returns['1y']}%
        </td>
        <td class="text-danger">${fund.risk_metrics['max_drawdown']}%</td>
        <td>${fund.risk_metrics['volatility']}%</td>
        <td>${fund.risk_metrics['sharpe_ratio']}</td>
      </tr>
    `).join('');
    
    resultContainer.innerHTML = `
      <div class="fund-analysis-card">
        <h3>基金对比结果</h3>
        
        <div class="fund-metrics-grid">
          <div class="fund-metric-item">
            <div class="fund-metric-label">最佳1年收益</div>
            <div class="fund-metric-value positive">
              ${summary.best_return_1y?.symbol}: +${summary.best_return_1y?.value}%
            </div>
          </div>
          <div class="fund-metric-item">
            <div class="fund-metric-label">最佳夏普比率</div>
            <div class="fund-metric-value">
              ${summary.best_sharpe?.symbol}: ${summary.best_sharpe?.value}
            </div>
          </div>
          <div class="fund-metric-item">
            <div class="fund-metric-label">最低回撤</div>
            <div class="fund-metric-value negative">
              ${summary.lowest_drawdown?.symbol}: ${summary.lowest_drawdown?.value}%
            </div>
          </div>
        </div>
        
        <div class="table-responsive">
          <table class="table table-hover fund-compare-table">
            <thead>
              <tr>
                <th>基金代码</th>
                <th>最新净值</th>
                <th>近1月</th>
                <th>近3月</th>
                <th>近1年</th>
                <th>最大回撤</th>
                <th>波动率</th>
                <th>夏普比率</th>
              </tr>
            </thead>
            <tbody>
              ${tableRows}
            </tbody>
          </table>
        </div>
      </div>
    `;
  },

  // 基金筛选
  async screenFunds(filters) {
    const resultContainer = document.getElementById('fund-screen-result');
    if (!resultContainer) return;
    
    resultContainer.innerHTML = '<div class="fund-loading"><div class="spinner-border" role="status"></div><p>正在筛选基金...</p></div>';
    
    try {
      const params = new URLSearchParams();
      if (filters.fund_type) params.append('fund_type', filters.fund_type);
      if (filters.min_return_1y) params.append('min_return_1y', filters.min_return_1y);
      if (filters.max_drawdown) params.append('max_drawdown', filters.max_drawdown);
      if (filters.min_sharpe) params.append('min_sharpe', filters.min_sharpe);
      if (filters.limit) params.append('limit', filters.limit);
      
      const response = await fetch(`/api/v1/fund/analysis/screen?${params}`);
      const data = await response.json();
      
      if (Array.isArray(data) && data.length > 0 && data[0].error) {
        resultContainer.innerHTML = `<div class="fund-screen-empty"><i class="bi bi-exclamation-circle"></i><p>${data[0].error}</p></div>`;
        return;
      }
      
      this.renderScreeningResults(data);
    } catch (error) {
      console.error('基金筛选失败:', error);
      resultContainer.innerHTML = '<div class="fund-screen-empty"><i class="bi bi-exclamation-circle"></i><p>基金筛选失败，请稍后重试</p></div>';
    }
  },

  // 渲染筛选结果
  renderScreeningResults(funds) {
    const resultContainer = document.getElementById('fund-screen-result');
    if (!resultContainer) return;
    
    if (!funds || funds.length === 0) {
      resultContainer.innerHTML = '<div class="fund-screen-empty"><i class="bi bi-search"></i><p>没有找到符合条件的基金</p></div>';
      return;
    }
    
    let tableRows = funds.map((fund, index) => `
      <tr>
        <td>${index + 1}</td>
        <td><strong>${fund.symbol}</strong></td>
        <td>${fund.name}</td>
        <td>${fund.fund_type}</td>
        <td>${fund.exchange}</td>
        <td>${fund.latest_nav}</td>
        <td class="${fund.returns['1y'] >= 0 ? 'text-success' : 'text-danger'}">
          ${fund.returns['1y'] >= 0 ? '+' : ''}${fund.returns['1y']}%
        </td>
        <td class="text-danger">${fund.risk_metrics['max_drawdown']}%</td>
        <td>${fund.risk_metrics['sharpe_ratio']}</td>
        <td>
          <button class="btn btn-sm btn-outline-primary" onclick="FundModule.loadFundAnalysis('${fund.symbol}')">
            分析
          </button>
          <button class="btn btn-sm btn-outline-secondary" onclick="FundModule.addToWatchlist('${fund.symbol}')">
            加入观察
          </button>
        </td>
      </tr>
    `).join('');
    
    resultContainer.innerHTML = `
      <div class="fund-analysis-card">
        <h3>筛选结果 (${funds.length} 只基金)</h3>
        
        <div class="table-responsive">
          <table class="table table-hover fund-screen-table">
            <thead>
              <tr>
                <th>排名</th>
                <th>代码</th>
                <th>名称</th>
                <th>类型</th>
                <th>交易所</th>
                <th>最新净值</th>
                <th>近1年收益</th>
                <th>最大回撤</th>
                <th>夏普比率</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              ${tableRows}
            </tbody>
          </table>
        </div>
      </div>
    `;
  },
};

// 导出模块
window.FundModule = FundModule;
