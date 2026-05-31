# 统一仪表盘设计文档 - 加密货币Tab页集成

> 生成日期：2026-05-30
> 版本：1.0

---

## 1. 项目概述

### 1.1 项目目标

在现有的A股仪表盘中添加加密货币Tab页，实现A股和加密货币的统一监控界面。

### 1.2 核心需求

- 在a-share-hub仪表盘中添加加密货币Tab页
- 显示加密货币的完整监控面板（技术指标、交易信号、持仓、订单、账户余额）
- 通过API代理调用crypto-hub的服务
- 数据实时更新

### 1.3 成功标准

1. 加密货币Tab页可以正常访问
2. 所有数据正确显示
3. 数据实时更新（每10秒刷新）
4. 与现有A股Tab页无缝切换

---

## 2. 架构设计

### 2.1 修改范围

1. 修改 `src/api/dashboard.html` - 添加加密货币Tab页
2. 修改 `src/api/routes_dashboard.py` - 添加加密货币API代理
3. 添加JavaScript代码 - 处理加密货币数据加载和刷新

### 2.2 数据流

```
用户访问 http://localhost:8000/dashboard
        ↓
点击"加密货币"Tab页
        ↓
前端通过API代理调用crypto-hub的API
        ↓
crypto-hub运行在 http://localhost:8001
        ↓
返回数据并显示在页面上
        ↓
每10秒自动刷新
```

### 2.3 技术栈

- **前端**：HTML + CSS + JavaScript（复用现有技术栈）
- **后端**：FastAPI + httpx（异步HTTP客户端）
- **数据源**：crypto-hub API（端口8001）

---

## 3. API设计

### 3.1 新增API代理端点

| 端点 | 方法 | 功能 | 代理目标 |
|------|------|------|----------|
| `/api/v1/crypto/status` | GET | 系统状态 | `http://localhost:8001/api/dashboard/status` |
| `/api/v1/crypto/balance` | GET | 账户余额 | `http://localhost:8001/api/dashboard/balance` |
| `/api/v1/crypto/positions` | GET | 当前持仓 | `http://localhost:8001/api/dashboard/positions` |
| `/api/v1/crypto/orders` | GET | 订单列表 | `http://localhost:8001/api/dashboard/orders` |
| `/api/v1/crypto/signals` | GET | 交易信号 | `http://localhost:8001/api/dashboard/signals` |
| `/api/v1/crypto/indicators/{symbol}` | GET | 技术指标 | `http://localhost:8001/api/dashboard/indicators/{symbol}` |

### 3.2 API响应格式

保持与crypto-hub相同的响应格式：

```json
{
  "success": true,
  "data": {...},
  "timestamp": "2026-05-30T10:00:00Z"
}
```

### 3.3 代理方式

- 使用httpx异步调用crypto-hub的API
- 超时设置：10秒
- 错误处理：返回500状态码和错误信息

---

## 4. 前端设计

### 4.1 Tab页布局

```
[A股实时行情] [加密货币] [决策历史] [回测] [选股扫描]
```

### 4.2 加密货币Tab页内容

```
+------------------+
| 系统状态 | 账户  |
+------------------+
| 技术指标 | 信号  |
+------------------+
| 持仓    | 订单  |
+------------------+
```

### 4.3 功能模块

1. **系统状态区** - 显示API连接状态、最后更新时间
2. **账户区** - 显示USDT余额、总资产
3. **技术指标区** - 显示MA5、MA10、MA20、RSI、MACD
4. **信号区** - 显示最新交易信号
5. **持仓区** - 显示当前持仓列表
6. **订单区** - 显示最近订单

### 4.4 自动刷新

- 每10秒自动刷新数据
- 使用JavaScript定时器
- 只在加密货币Tab页激活时刷新

---

## 5. 实现计划

### 5.1 阶段1：后端API代理（1天）

- [ ] 修改routes_dashboard.py，添加加密货币API代理端点
- [ ] 使用httpx调用crypto-hub的API
- [ ] 测试API代理功能

### 5.2 阶段2：前端Tab页（1-2天）

- [ ] 修改dashboard.html，添加加密货币Tab页
- [ ] 添加加密货币监控面板HTML
- [ ] 添加CSS样式

### 5.3 阶段3：JavaScript集成（1天）

- [ ] 添加加密货币数据加载函数
- [ ] 添加自动刷新功能
- [ ] 错误处理

### 5.4 阶段4：测试和优化（0.5天）

- [ ] 功能测试
- [ ] 性能优化

---

## 6. 风险评估

### 6.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| crypto-hub服务不可用 | 高 | 添加错误处理和重试机制 |
| API调用超时 | 中 | 设置合理的超时时间 |
| 数据格式不匹配 | 中 | 添加数据验证和转换 |

### 6.2 业务风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 数据不准确 | 高 | 添加数据验证和校验 |
| 系统故障 | 中 | 添加监控和告警 |

---

## 7. 总结

本设计文档详细描述了在a-share-hub仪表盘中添加加密货币Tab页的架构、API设计、前端设计和实现计划。通过API代理方式，可以快速实现A股和加密货币的统一监控界面。

预计总工时：3.5-4.5天

---

## 附录

### A. 参考文档

- [a-share-hub仪表盘实现](src/api/routes_dashboard.py)
- [crypto-hub仪表盘实现](crypto-hub/src/api/routes_dashboard.py)
- [httpx文档](https://www.python-httpx.org/)

### B. 术语表

- **API代理**：通过后端服务转发前端请求到其他服务
- **Tab页**：页面中的标签页，用于切换不同内容
- **自动刷新**：定时自动更新页面数据
