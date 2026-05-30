// 全局变量
let refreshInterval = null;
const REFRESH_RATE = 10000; // 10秒刷新一次

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    initDashboard();
    startAutoRefresh();
});

// 初始化仪表盘
function initDashboard() {
    loadSystemStatus();
    loadBalance();
    loadIndicators('BTCUSDT');
    loadSignals();
    loadPositions();
    loadOrders();
}

// 开始自动刷新
function startAutoRefresh() {
    refreshInterval = setInterval(function() {
        loadSystemStatus();
        loadBalance();
        loadPositions();
        loadOrders();
    }, REFRESH_RATE);
}

// 停止自动刷新
function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// 加载系统状态
async function loadSystemStatus() {
    try {
        const response = await fetch('/api/dashboard/status');
        const data = await response.json();

        if (data.success) {
            document.getElementById('api-status').textContent = '已连接';
            document.getElementById('api-status').className = 'badge bg-success';
            document.getElementById('uptime').textContent = data.data.uptime;
            document.getElementById('last-update').textContent = new Date(data.timestamp).toLocaleString();
        }
    } catch (error) {
        console.error('加载系统状态失败:', error);
        document.getElementById('api-status').textContent = '连接失败';
        document.getElementById('api-status').className = 'badge bg-danger';
    }
}

// 加载账户余额
async function loadBalance() {
    try {
        const response = await fetch('/api/dashboard/balance');
        const data = await response.json();

        if (data.success) {
            document.getElementById('usdt-balance').textContent = data.data.usdt_balance.toFixed(2) + ' USDT';
            document.getElementById('total-assets').textContent = data.data.total_assets.toFixed(2) + ' USDT';
        }
    } catch (error) {
        console.error('加载账户余额失败:', error);
    }
}

// 加载技术指标
async function loadIndicators(symbol) {
    try {
        const response = await fetch(`/api/dashboard/indicators/${symbol}`);
        const data = await response.json();

        if (data.success) {
            document.getElementById('ma5').textContent = data.data.ma5.toFixed(2);
            document.getElementById('ma10').textContent = data.data.ma10.toFixed(2);
            document.getElementById('ma20').textContent = data.data.ma20.toFixed(2);
            document.getElementById('rsi').textContent = data.data.rsi.toFixed(2);
            document.getElementById('macd').textContent = data.data.macd.macd.toFixed(2);
        }
    } catch (error) {
        console.error('加载技术指标失败:', error);
    }
}

// 加载交易信号
async function loadSignals() {
    try {
        const response = await fetch('/api/dashboard/signals');
        const data = await response.json();

        if (data.success) {
            const signalsDiv = document.getElementById('signals');
            if (data.data.length === 0) {
                signalsDiv.innerHTML = '<p class="text-muted">暂无交易信号</p>';
            } else {
                let html = '<div class="list-group">';
                data.data.forEach(signal => {
                    html += `<div class="list-group-item">
                        <strong>${signal.symbol}</strong> - ${signal.action}
                        <br><small class="text-muted">${signal.reason}</small>
                    </div>`;
                });
                html += '</div>';
                signalsDiv.innerHTML = html;
            }
        }
    } catch (error) {
        console.error('加载交易信号失败:', error);
    }
}

// 加载持仓
async function loadPositions() {
    try {
        const response = await fetch('/api/dashboard/positions');
        const data = await response.json();

        if (data.success) {
            const positionsDiv = document.getElementById('positions');
            if (data.data.length === 0) {
                positionsDiv.innerHTML = '<p class="text-muted">暂无持仓</p>';
            } else {
                let html = '<div class="table-responsive"><table class="table table-sm">';
                html += '<thead><tr><th>币种</th><th>数量</th><th>成本</th><th>盈亏</th></tr></thead>';
                html += '<tbody>';
                data.data.forEach(pos => {
                    const pnlClass = pos.unrealized_pnl >= 0 ? 'text-success' : 'text-danger';
                    html += `<tr>
                        <td>${pos.symbol}</td>
                        <td>${pos.quantity}</td>
                        <td>${pos.avg_cost}</td>
                        <td class="${pnlClass}">${pos.unrealized_pnl}</td>
                    </tr>`;
                });
                html += '</tbody></table></div>';
                positionsDiv.innerHTML = html;
            }
        }
    } catch (error) {
        console.error('加载持仓失败:', error);
    }
}

// 加载订单
async function loadOrders() {
    try {
        const response = await fetch('/api/dashboard/orders');
        const data = await response.json();

        if (data.success) {
            const ordersDiv = document.getElementById('orders');
            if (data.data.length === 0) {
                ordersDiv.innerHTML = '<p class="text-muted">暂无订单</p>';
            } else {
                let html = '<div class="table-responsive"><table class="table table-sm">';
                html += '<thead><tr><th>币种</th><th>方向</th><th>数量</th><th>价格</th><th>状态</th></tr></thead>';
                html += '<tbody>';
                data.data.forEach(order => {
                    const sideClass = order.side === 'BUY' ? 'text-success' : 'text-danger';
                    html += `<tr>
                        <td>${order.symbol}</td>
                        <td class="${sideClass}">${order.side}</td>
                        <td>${order.quantity}</td>
                        <td>${order.price}</td>
                        <td>${order.status}</td>
                    </tr>`;
                });
                html += '</tbody></table></div>';
                ordersDiv.innerHTML = html;
            }
        }
    } catch (error) {
        console.error('加载订单失败:', error);
    }
}
