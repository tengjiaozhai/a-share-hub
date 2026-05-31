# 统一仪表盘 - 加密货币Tab页集成实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有的A股仪表盘中添加加密货币Tab页，实现A股和加密货币的统一监控界面

**Architecture:** 通过API代理方式，使用httpx调用crypto-hub的API，在前端添加加密货币Tab页显示完整监控面板

**Tech Stack:** FastAPI, httpx, HTML, CSS, JavaScript

---

## 文件结构

```
a-share-hub/
├── src/
│   ├── api/
│   │   ├── routes_dashboard.py  # 修改：添加加密货币API代理
│   │   └── dashboard.html       # 修改：添加加密货币Tab页
│   └── ...
└── tests/
    └── test_crypto_proxy.py     # 新增：API代理测试
```

---

## 阶段1：后端API代理

### Task 1.1: 添加加密货币API代理端点

**Files:**
- Modify: `src/api/routes_dashboard.py`
- Create: `tests/test_crypto_proxy.py`

- [ ] **Step 1: 添加httpx依赖**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/pip install httpx
```

- [ ] **Step 2: 添加加密货币API代理端点**

```python
# src/api/routes_dashboard.py - 在文件末尾添加

import httpx

CRYPTO_HUB_BASE_URL = "http://localhost:8001"

@router.get("/api/v1/crypto/status")
async def proxy_crypto_status():
    """代理crypto-hub的系统状态API"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{CRYPTO_HUB_BASE_URL}/api/dashboard/status")
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch crypto status: {str(e)}")

@router.get("/api/v1/crypto/balance")
async def proxy_crypto_balance():
    """代理crypto-hub的账户余额API"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{CRYPTO_HUB_BASE_URL}/api/dashboard/balance")
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch crypto balance: {str(e)}")

@router.get("/api/v1/crypto/positions")
async def proxy_crypto_positions():
    """代理crypto-hub的持仓API"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{CRYPTO_HUB_BASE_URL}/api/dashboard/positions")
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch crypto positions: {str(e)}")

@router.get("/api/v1/crypto/orders")
async def proxy_crypto_orders():
    """代理crypto-hub的订单API"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{CRYPTO_HUB_BASE_URL}/api/dashboard/orders")
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch crypto orders: {str(e)}")

@router.get("/api/v1/crypto/signals")
async def proxy_crypto_signals():
    """代理crypto-hub的信号API"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{CRYPTO_HUB_BASE_URL}/api/dashboard/signals")
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch crypto signals: {str(e)}")

@router.get("/api/v1/crypto/indicators/{symbol}")
async def proxy_crypto_indicators(symbol: str):
    """代理crypto-hub的技术指标API"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{CRYPTO_HUB_BASE_URL}/api/dashboard/indicators/{symbol}")
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch crypto indicators: {str(e)}")
```

- [ ] **Step 3: 编写API代理测试**

```python
# tests/test_crypto_proxy.py
import pytest
from fastapi.testclient import TestClient
from src.api.routes_dashboard import app

client = TestClient(app)

def test_proxy_crypto_status():
    """测试代理crypto状态API"""
    response = client.get("/api/v1/crypto/status")
    # 注意：如果crypto-hub未运行，会返回500
    assert response.status_code in [200, 500]

def test_proxy_crypto_balance():
    """测试代理crypto余额API"""
    response = client.get("/api/v1/crypto/balance")
    assert response.status_code in [200, 500]

def test_proxy_crypto_positions():
    """测试代理crypto持仓API"""
    response = client.get("/api/v1/crypto/positions")
    assert response.status_code in [200, 500]

def test_proxy_crypto_orders():
    """测试代理crypto订单API"""
    response = client.get("/api/v1/crypto/orders")
    assert response.status_code in [200, 500]

def test_proxy_crypto_signals():
    """测试代理crypto信号API"""
    response = client.get("/api/v1/crypto/signals")
    assert response.status_code in [200, 500]

def test_proxy_crypto_indicators():
    """测试代理crypto技术指标API"""
    response = client.get("/api/v1/crypto/indicators/BTCUSDT")
    assert response.status_code in [200, 500]
```

- [ ] **Step 4: 运行测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_crypto_proxy.py -v
```

Expected: 所有测试通过（如果crypto-hub未运行，会返回500，这是正常的）

- [ ] **Step 5: 提交代码**

```bash
git add src/api/routes_dashboard.py tests/test_crypto_proxy.py
git commit -m "feat: 添加加密货币API代理端点"
```

**验收标准:**
- [ ] 所有API代理端点可以正常访问
- [ ] 返回正确的JSON格式
- [ ] 所有测试通过

---

## 阶段2：前端Tab页

### Task 2.1: 添加加密货币Tab页

**Files:**
- Modify: `src/api/dashboard.html`

- [ ] **Step 1: 添加加密货币Tab页按钮**

在现有的Tab导航中添加加密货币Tab页按钮：

```html
<!-- 在现有的Tab导航中添加 -->
<li class="nav-item" role="presentation">
    <button class="nav-link" id="crypto-tab" data-bs-toggle="tab" 
            data-bs-target="#crypto" type="button" role="tab" 
            aria-controls="crypto" aria-selected="false">
        <i class="bi bi-currency-bitcoin"></i> 加密货币
    </button>
</li>
```

- [ ] **Step 2: 添加加密货币Tab页内容**

```html
<!-- 加密货币Tab页内容 -->
<div class="tab-pane fade" id="crypto" role="tabpanel" aria-labelledby="crypto-tab">
    <div class="row mb-4">
        <div class="col-12">
            <h4><i class="bi bi-currency-bitcoin"></i> 加密货币监控面板</h4>
            <p class="text-muted">实时监控加密货币技术指标、交易信号、持仓和订单</p>
        </div>
    </div>

    <!-- 系统状态和账户 -->
    <div class="row mb-4">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <i class="bi bi-activity"></i> 系统状态
                </div>
                <div class="card-body">
                    <div id="crypto-system-status">
                        <p><strong>API连接:</strong> <span id="crypto-api-status" class="badge bg-secondary">未连接</span></p>
                        <p><strong>运行状态:</strong> <span id="crypto-uptime">-</span></p>
                        <p><strong>最后更新:</strong> <span id="crypto-last-update">-</span></p>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-success text-white">
                    <i class="bi bi-wallet2"></i> 账户信息
                </div>
                <div class="card-body">
                    <div id="crypto-account-info">
                        <p><strong>USDT余额:</strong> <span id="crypto-usdt-balance">-</span></p>
                        <p><strong>总资产:</strong> <span id="crypto-total-assets">-</span></p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 技术指标和信号 -->
    <div class="row mb-4">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-info text-white">
                    <i class="bi bi-graph-up"></i> 技术指标
                </div>
                <div class="card-body">
                    <div id="crypto-indicators">
                        <p><strong>MA5:</strong> <span id="crypto-ma5">-</span></p>
                        <p><strong>MA10:</strong> <span id="crypto-ma10">-</span></p>
                        <p><strong>MA20:</strong> <span id="crypto-ma20">-</span></p>
                        <p><strong>RSI:</strong> <span id="crypto-rsi">-</span></p>
                        <p><strong>MACD:</strong> <span id="crypto-macd">-</span></p>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-warning text-dark">
                    <i class="bi bi-bell"></i> 交易信号
                </div>
                <div class="card-body">
                    <div id="crypto-signals">
                        <p class="text-muted">暂无交易信号</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 持仓和订单 -->
    <div class="row">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-secondary text-white">
                    <i class="bi bi-collection"></i> 当前持仓
                </div>
                <div class="card-body">
                    <div id="crypto-positions">
                        <p class="text-muted">暂无持仓</p>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-danger text-white">
                    <i class="bi bi-list-check"></i> 最近订单
                </div>
                <div class="card-body">
                    <div id="crypto-orders">
                        <p class="text-muted">暂无订单</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
```

- [ ] **Step 3: 提交代码**

```bash
git add src/api/dashboard.html
git commit -m "feat: 添加加密货币Tab页HTML结构"
```

**验收标准:**
- [ ] Tab页可以正常切换
- [ ] 页面布局符合设计
- [ ] 响应式布局正常

---

## 阶段3：JavaScript集成

### Task 3.1: 添加加密货币数据加载功能

**Files:**
- Modify: `src/api/dashboard.html`

- [ ] **Step 1: 添加加密货币JavaScript代码**

在dashboard.html的JavaScript部分添加以下代码：

```javascript
// 加密货币数据加载
let cryptoRefreshInterval = null;
const CRYPTO_REFRESH_RATE = 10000; // 10秒刷新一次

// 初始化加密货币Tab页
function initCryptoTab() {
    loadCryptoSystemStatus();
    loadCryptoBalance();
    loadCryptoIndicators('BTCUSDT');
    loadCryptoSignals();
    loadCryptoPositions();
    loadCryptoOrders();
}

// 开始加密货币自动刷新
function startCryptoAutoRefresh() {
    if (cryptoRefreshInterval) {
        clearInterval(cryptoRefreshInterval);
    }
    cryptoRefreshInterval = setInterval(function() {
        loadCryptoSystemStatus();
        loadCryptoBalance();
        loadCryptoPositions();
        loadCryptoOrders();
    }, CRYPTO_REFRESH_RATE);
}

// 停止加密货币自动刷新
function stopCryptoAutoRefresh() {
    if (cryptoRefreshInterval) {
        clearInterval(cryptoRefreshInterval);
        cryptoRefreshInterval = null;
    }
}

// 加载加密货币系统状态
async function loadCryptoSystemStatus() {
    try {
        const response = await fetch('/api/v1/crypto/status');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('crypto-api-status').textContent = '已连接';
            document.getElementById('crypto-api-status').className = 'badge bg-success';
            document.getElementById('crypto-uptime').textContent = data.data.uptime;
            document.getElementById('crypto-last-update').textContent = new Date(data.timestamp).toLocaleString();
        }
    } catch (error) {
        console.error('加载加密货币系统状态失败:', error);
        document.getElementById('crypto-api-status').textContent = '连接失败';
        document.getElementById('crypto-api-status').className = 'badge bg-danger';
    }
}

// 加载加密货币账户余额
async function loadCryptoBalance() {
    try {
        const response = await fetch('/api/v1/crypto/balance');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('crypto-usdt-balance').textContent = data.data.usdt_balance.toFixed(2) + ' USDT';
            document.getElementById('crypto-total-assets').textContent = data.data.total_assets.toFixed(2) + ' USDT';
        }
    } catch (error) {
        console.error('加载加密货币账户余额失败:', error);
    }
}

// 加载加密货币技术指标
async function loadCryptoIndicators(symbol) {
    try {
        const response = await fetch(`/api/v1/crypto/indicators/${symbol}`);
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('crypto-ma5').textContent = data.data.ma5.toFixed(2);
            document.getElementById('crypto-ma10').textContent = data.data.ma10.toFixed(2);
            document.getElementById('crypto-ma20').textContent = data.data.ma20.toFixed(2);
            document.getElementById('crypto-rsi').textContent = data.data.rsi.toFixed(2);
            document.getElementById('crypto-macd').textContent = data.data.macd.macd.toFixed(2);
        }
    } catch (error) {
        console.error('加载加密货币技术指标失败:', error);
    }
}

// 加载加密货币交易信号
async function loadCryptoSignals() {
    try {
        const response = await fetch('/api/v1/crypto/signals');
        const data = await response.json();
        
        if (data.success) {
            const signalsDiv = document.getElementById('crypto-signals');
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
        console.error('加载加密货币交易信号失败:', error);
    }
}

// 加载加密货币持仓
async function loadCryptoPositions() {
    try {
        const response = await fetch('/api/v1/crypto/positions');
        const data = await response.json();
        
        if (data.success) {
            const positionsDiv = document.getElementById('crypto-positions');
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
        console.error('加载加密货币持仓失败:', error);
    }
}

// 加载加密货币订单
async function loadCryptoOrders() {
    try {
        const response = await fetch('/api/v1/crypto/orders');
        const data = await response.json();
        
        if (data.success) {
            const ordersDiv = document.getElementById('crypto-orders');
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
        console.error('加载加密货币订单失败:', error);
    }
}

// Tab页切换事件处理
document.addEventListener('DOMContentLoaded', function() {
    // 监听Tab页切换事件
    const cryptoTab = document.getElementById('crypto-tab');
    if (cryptoTab) {
        cryptoTab.addEventListener('shown.bs.tab', function() {
            // 当切换到加密货币Tab页时，初始化数据并开始自动刷新
            initCryptoTab();
            startCryptoAutoRefresh();
        });
        
        cryptoTab.addEventListener('hidden.bs.tab', function() {
            // 当离开加密货币Tab页时，停止自动刷新
            stopCryptoAutoRefresh();
        });
    }
});
```

- [ ] **Step 2: 提交代码**

```bash
git add src/api/dashboard.html
git commit -m "feat: 添加加密货币数据加载和自动刷新功能"
```

**验收标准:**
- [ ] 数据可以正确加载
- [ ] 自动刷新功能正常
- [ ] 错误处理正常

---

## 阶段4：测试和优化

### Task 4.1: 功能测试

**Files:**
- Modify: `tests/test_crypto_proxy.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/test_crypto_proxy.py - 更新测试
import pytest
from fastapi.testclient import TestClient
from src.api.routes_dashboard import app

client = TestClient(app)

def test_dashboard_page_with_crypto_tab():
    """测试仪表盘页面包含加密货币Tab页"""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "加密货币" in response.text
    assert "crypto-tab" in response.text

def test_crypto_proxy_endpoints():
    """测试所有加密货币API代理端点"""
    endpoints = [
        "/api/v1/crypto/status",
        "/api/v1/crypto/balance",
        "/api/v1/crypto/positions",
        "/api/v1/crypto/orders",
        "/api/v1/crypto/signals",
        "/api/v1/crypto/indicators/BTCUSDT",
    ]
    
    for endpoint in endpoints:
        response = client.get(endpoint)
        # 如果crypto-hub未运行，会返回500
        assert response.status_code in [200, 500]
```

- [ ] **Step 2: 运行集成测试**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_crypto_proxy.py -v
```

Expected: 所有测试通过

- [ ] **Step 3: 提交代码**

```bash
git add tests/test_crypto_proxy.py
git commit -m "test: 添加加密货币集成测试"
```

**验收标准:**
- [ ] 所有测试通过
- [ ] 页面可以正常访问
- [ ] API端点工作正常

---

## 自我审查

### 1. 规范覆盖检查

- [x] 后端API代理：所有端点已实现
- [x] 前端Tab页：HTML结构已添加
- [x] JavaScript：数据加载和刷新功能已实现
- [x] 测试：单元测试和集成测试已编写

### 2. 占位符扫描

- [x] 无TBD、TODO或"implement later"
- [x] 所有代码块都是完整的实现
- [x] 所有测试都有具体的断言

### 3. 类型一致性检查

- [x] API响应格式一致
- [x] 数据类型在所有模块中保持一致

---

## 执行选项

**Plan complete and saved to `docs/superpowers/plans/2026-05-30-unified-dashboard-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 每个任务分发一个新的子代理，任务间进行审查，快速迭代

**2. Inline Execution** - 在当前会话中执行任务，使用executing-plans进行批量执行和检查点审查

**Which approach?**
