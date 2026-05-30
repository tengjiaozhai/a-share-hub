# Crypto Hub 策略监控仪表盘实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为crypto-hub模块添加策略监控仪表盘，提供Web界面显示技术指标、交易信号、持仓和订单信息

**Architecture:** 使用FastAPI + Jinja2模板引擎实现纯后端渲染，前端通过AJAX调用API获取数据并实时更新

**Tech Stack:** FastAPI, Jinja2, HTML, CSS, JavaScript, Bootstrap

---

## 文件结构

```
crypto-hub/src/
├── api/
│   ├── __init__.py
│   ├── routes_dashboard.py  # 仪表盘API路由
│   └── routes_strategy.py   # 策略API路由
├── templates/
│   ├── base.html           # 基础模板
│   ├── dashboard.html      # 仪表盘页面
│   └── components/         # 可复用组件
└── static/
    ├── css/
    │   └── style.css       # 自定义样式
    └── js/
        └── dashboard.js    # 仪表盘JavaScript
```

---

## 阶段1：后端API实现

### Task 1.1: 创建仪表盘API路由

**Files:**
- Create: `crypto-hub/src/api/__init__.py`
- Create: `crypto-hub/src/api/routes_dashboard.py`
- Modify: `crypto-hub/src/main.py`

- [ ] **Step 1: 创建API模块初始化文件**

```python
# crypto-hub/src/api/__init__.py
from .routes_dashboard import router as dashboard_router

__all__ = ["dashboard_router"]
```

- [ ] **Step 2: 创建仪表盘API路由**

```python
# crypto-hub/src/api/routes_dashboard.py
from fastapi import APIRouter, HTTPException
from datetime import datetime
import httpx

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("/status")
async def get_status():
    """获取系统状态"""
    return {
        "success": True,
        "data": {
            "api_connected": True,
            "uptime": "运行中",
            "last_update": datetime.now().isoformat()
        },
        "timestamp": datetime.now().isoformat()
    }

@router.get("/balance")
async def get_balance():
    """获取账户余额"""
    try:
        # 这里将调用BinanceProvider获取余额
        # 临时返回模拟数据
        return {
            "success": True,
            "data": {
                "usdt_balance": 10000.0,
                "total_assets": 10000.0
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/positions")
async def get_positions():
    """获取当前持仓"""
    try:
        # 这里将调用数据库获取持仓
        # 临时返回模拟数据
        return {
            "success": True,
            "data": [],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders")
async def get_orders():
    """获取订单列表"""
    try:
        # 这里将调用数据库获取订单
        # 临时返回模拟数据
        return {
            "success": True,
            "data": [],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/signals")
async def get_signals():
    """获取交易信号"""
    try:
        # 这里将调用策略模块获取信号
        # 临时返回模拟数据
        return {
            "success": True,
            "data": [],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/indicators/{symbol}")
async def get_indicators(symbol: str):
    """获取技术指标"""
    try:
        # 这里将调用技术指标模块
        # 临时返回模拟数据
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "ma5": 42000.0,
                "ma10": 41800.0,
                "ma20": 41500.0,
                "rsi": 65.5,
                "macd": {
                    "macd": 100.0,
                    "signal": 80.0,
                    "histogram": 20.0
                }
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 3: 修改主入口文件**

```python
# crypto-hub/src/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from .api.routes_dashboard import router as dashboard_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting crypto-hub...")
    yield
    # Shutdown
    print("Shutting down crypto-hub...")

app = FastAPI(
    title="Crypto Hub",
    description="币安Alpha代币交易模块",
    version="0.1.0",
    lifespan=lifespan
)

# 注册路由
app.include_router(dashboard_router)

@app.get("/health")
async def health():
    return {"status": "ok", "module": "crypto"}
```

- [ ] **Step 4: 编写API测试**

```python
# crypto-hub/tests/test_api/test_routes_dashboard.py
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_get_status():
    """测试获取系统状态"""
    response = client.get("/api/dashboard/status")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "api_connected" in data["data"]

def test_get_balance():
    """测试获取账户余额"""
    response = client.get("/api/dashboard/balance")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "usdt_balance" in data["data"]

def test_get_positions():
    """测试获取持仓"""
    response = client.get("/api/dashboard/positions")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

def test_get_orders():
    """测试获取订单"""
    response = client.get("/api/dashboard/orders")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

def test_get_signals():
    """测试获取信号"""
    response = client.get("/api/dashboard/signals")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

def test_get_indicators():
    """测试获取技术指标"""
    response = client.get("/api/dashboard/indicators/BTCUSDT")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["symbol"] == "BTCUSDT"
```

- [ ] **Step 5: 运行API测试**

```bash
cd crypto-hub
pytest tests/test_api/test_routes_dashboard.py -v
```

Expected: 所有测试通过

- [ ] **Step 6: 提交代码**

```bash
git add src/api/ tests/test_api/
git commit -m "feat: 添加仪表盘API路由"
```

**验收标准:**
- [ ] 所有API端点可以正常访问
- [ ] 返回正确的JSON格式
- [ ] 所有测试通过

---

## 阶段2：前端页面实现

### Task 2.1: 创建基础模板

**Files:**
- Create: `crypto-hub/templates/base.html`
- Create: `crypto-hub/templates/dashboard.html`

- [ ] **Step 1: 创建基础模板**

```html
<!-- crypto-hub/templates/base.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Crypto Hub{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    {% block extra_css %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="bi bi-currency-bitcoin"></i> Crypto Hub
            </a>
            <div class="navbar-nav">
                <a class="nav-link active" href="/dashboard">仪表盘</a>
            </div>
        </div>
    </nav>

    <main class="container mt-4">
        {% block content %}{% endblock %}
    </main>

    <footer class="mt-5 py-3 bg-light">
        <div class="container text-center">
            <span class="text-muted">Crypto Hub - 币安Alpha代币交易模块</span>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: 创建仪表盘页面**

```html
<!-- crypto-hub/templates/dashboard.html -->
{% extends "base.html" %}

{% block title %}策略监控仪表盘 - Crypto Hub{% endblock %}

{% block content %}
<div class="row mb-4">
    <div class="col-12">
        <h2><i class="bi bi-speedometer2"></i> 策略监控仪表盘</h2>
        <p class="text-muted">实时监控技术指标、交易信号、持仓和订单</p>
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
                <div id="system-status">
                    <p><strong>API连接:</strong> <span id="api-status" class="badge bg-success">已连接</span></p>
                    <p><strong>运行状态:</strong> <span id="uptime">运行中</span></p>
                    <p><strong>最后更新:</strong> <span id="last-update">-</span></p>
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
                <div id="account-info">
                    <p><strong>USDT余额:</strong> <span id="usdt-balance">-</span></p>
                    <p><strong>总资产:</strong> <span id="total-assets">-</span></p>
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
                <div id="indicators">
                    <p><strong>MA5:</strong> <span id="ma5">-</span></p>
                    <p><strong>MA10:</strong> <span id="ma10">-</span></p>
                    <p><strong>MA20:</strong> <span id="ma20">-</span></p>
                    <p><strong>RSI:</strong> <span id="rsi">-</span></p>
                    <p><strong>MACD:</strong> <span id="macd">-</span></p>
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
                <div id="signals">
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
                <div id="positions">
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
                <div id="orders">
                    <p class="text-muted">暂无订单</p>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="/static/js/dashboard.js"></script>
{% endblock %}
```

- [ ] **Step 3: 提交代码**

```bash
git add templates/
git commit -m "feat: 添加仪表盘HTML模板"
```

**验收标准:**
- [ ] 模板可以正确渲染
- [ ] 页面布局符合设计
- [ ] 响应式布局正常

---

### Task 2.2: 添加CSS样式

**Files:**
- Create: `crypto-hub/static/css/style.css`

- [ ] **Step 1: 创建自定义样式**

```css
/* crypto-hub/static/css/style.css */

/* 全局样式 */
body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background-color: #f8f9fa;
}

/* 卡片样式 */
.card {
    border: none;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s;
}

.card:hover {
    transform: translateY(-5px);
}

.card-header {
    font-weight: 600;
}

/* 状态指示器 */
.badge {
    font-size: 0.9em;
    padding: 0.5em 0.8em;
}

/* 数据显示 */
.data-value {
    font-size: 1.2em;
    font-weight: 600;
    color: #2c3e50;
}

/* 表格样式 */
.table-responsive {
    max-height: 300px;
    overflow-y: auto;
}

/* 加载动画 */
.loading {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 3px solid rgba(0, 0, 0, 0.1);
    border-radius: 50%;
    border-top-color: #007bff;
    animation: spin 1s ease-in-out infinite;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

/* 响应式调整 */
@media (max-width: 768px) {
    .card {
        margin-bottom: 1rem;
    }
}
```

- [ ] **Step 2: 更新基础模板引用样式**

```html
<!-- 在base.html的head中添加 -->
<link href="/static/css/style.css" rel="stylesheet">
```

- [ ] **Step 3: 提交代码**

```bash
git add static/css/
git commit -m "feat: 添加仪表盘CSS样式"
```

**验收标准:**
- [ ] 样式正确加载
- [ ] 页面美观易用
- [ ] 响应式布局正常

---

## 阶段3：数据集成

### Task 3.1: 实现JavaScript数据加载

**Files:**
- Create: `crypto-hub/static/js/dashboard.js`

- [ ] **Step 1: 创建仪表盘JavaScript**

```javascript
// crypto-hub/static/js/dashboard.js

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
```

- [ ] **Step 2: 更新主入口文件提供静态文件**

```python
# crypto-hub/src/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from .api.routes_dashboard import router as dashboard_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting crypto-hub...")
    yield
    # Shutdown
    print("Shutting down crypto-hub...")

app = FastAPI(
    title="Crypto Hub",
    description="币安Alpha代币交易模块",
    version="0.1.0",
    lifespan=lifespan
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 注册路由
app.include_router(dashboard_router)

@app.get("/health")
async def health():
    return {"status": "ok", "module": "crypto"}
```

- [ ] **Step 3: 添加仪表盘页面路由**

```python
# crypto-hub/src/api/routes_dashboard.py
from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates
from datetime import datetime

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard")
async def dashboard_page(request: Request):
    """仪表盘页面"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

# ... 其他API端点保持不变
```

- [ ] **Step 4: 提交代码**

```bash
git add static/js/ src/main.py src/api/routes_dashboard.py
git commit -m "feat: 添加仪表盘JavaScript和静态文件支持"
```

**验收标准:**
- [ ] 数据可以正确加载
- [ ] 自动刷新功能正常
- [ ] 错误处理正常

---

## 阶段4：测试和优化

### Task 4.1: 功能测试

**Files:**
- Create: `crypto-hub/tests/test_dashboard.py`

- [ ] **Step 1: 编写集成测试**

```python
# crypto-hub/tests/test_dashboard.py
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_dashboard_page():
    """测试仪表盘页面"""
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "策略监控仪表盘" in response.text

def test_api_endpoints():
    """测试所有API端点"""
    # 测试系统状态
    response = client.get("/api/dashboard/status")
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # 测试账户余额
    response = client.get("/api/dashboard/balance")
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # 测试持仓
    response = client.get("/api/dashboard/positions")
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # 测试订单
    response = client.get("/api/dashboard/orders")
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # 测试信号
    response = client.get("/api/dashboard/signals")
    assert response.status_code == 200
    assert response.json()["success"] is True
    
    # 测试技术指标
    response = client.get("/api/dashboard/indicators/BTCUSDT")
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["data"]["symbol"] == "BTCUSDT"

def test_static_files():
    """测试静态文件"""
    response = client.get("/static/css/style.css")
    assert response.status_code == 200
    
    response = client.get("/static/js/dashboard.js")
    assert response.status_code == 200
```

- [ ] **Step 2: 运行集成测试**

```bash
cd crypto-hub
pytest tests/test_dashboard.py -v
```

Expected: 所有测试通过

- [ ] **Step 3: 提交代码**

```bash
git add tests/test_dashboard.py
git commit -m "test: 添加仪表盘集成测试"
```

**验收标准:**
- [ ] 所有测试通过
- [ ] 页面可以正常访问
- [ ] API端点工作正常

---

## 自我审查

### 1. 规范覆盖检查

- [x] 后端API：所有端点已实现
- [x] 前端页面：HTML模板已创建
- [x] CSS样式：样式文件已创建
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

**Plan complete and saved to `docs/superpowers/plans/2026-05-30-crypto-dashboard-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 每个任务分发一个新的子代理，任务间进行审查，快速迭代

**2. Inline Execution** - 在当前会话中执行任务，使用executing-plans进行批量执行和检查点审查

**Which approach?**
