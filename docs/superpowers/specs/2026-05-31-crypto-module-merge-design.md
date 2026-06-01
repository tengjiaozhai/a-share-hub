# 加密货币模块合并到主服务设计文档

> 生成日期：2026-05-31
> 版本：1.0

---

## 1. 项目概述

### 1.1 项目目标

将加密货币模块从独立服务（crypto-hub, 端口8001）合并到主服务（a-share-hub, 端口8000），统一服务架构。

### 1.2 核心需求

- 将crypto-hub的代码合并到a-share-hub
- 统一使用8000端口
- 通过目录结构分类管理
- 移除API代理层
- 保持功能完整性

### 1.3 成功标准

1. 所有加密货币功能正常工作
2. 单一服务运行在8000端口
3. 代码组织清晰
4. 测试全部通过

---

## 2. 架构设计

### 2.1 重构前架构

```
a-share-hub (8000)
├── src/
│   ├── api/routes_dashboard.py  # 包含API代理
│   └── ...
└── crypto-hub (8001)
    └── src/
        ├── api/routes_dashboard.py
        ├── data/
        ├── execution/
        └── ...

问题：
- 两个服务，两个端口
- 需要API代理转发
- 部署复杂
```

### 2.2 重构后架构

```
a-share-hub (8000)
├── src/
│   ├── api/
│   │   ├── routes_crypto.py    # 加密货币API路由（新增）
│   │   └── ...
│   ├── crypto/                 # 加密货币模块（新增）
│   │   ├── __init__.py
│   │   ├── data/
│   │   │   ├── __init__.py
│   │   │   ├── binance_provider.py
│   │   │   ├── websocket_manager.py
│   │   │   └── data_cache.py
│   │   ├── execution/
│   │   │   ├── __init__.py
│   │   │   ├── binance_client.py
│   │   │   └── order_manager.py
│   │   ├── strategy/
│   │   │   ├── __init__.py
│   │   │   ├── indicators.py
│   │   │   └── signal_fusion.py
│   │   └── risk/
│   │       ├── __init__.py
│   │       └── risk_manager.py
│   └── ...
└── ...

优势：
- 单一服务，单一端口
- 无需API代理
- 共享配置、数据库
- 部署简单
```

### 2.3 目录结构

```
crypto/
├── __init__.py
├── data/
│   ├── __init__.py
│   ├── binance_provider.py    # 币安数据提供者
│   ├── websocket_manager.py   # WebSocket管理器
│   └── data_cache.py          # 数据缓存
├── execution/
│   ├── __init__.py
│   ├── binance_client.py      # 币安API客户端
│   └── order_manager.py       # 订单管理器
├── strategy/
│   ├── __init__.py
│   ├── indicators.py          # 技术指标
│   └── signal_fusion.py       # 信号融合
└── risk/
    ├── __init__.py
    └── risk_manager.py        # 风险管理器
```

---

## 3. API设计

### 3.1 新增API端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/crypto/status` | GET | 系统状态 |
| `/api/crypto/balance` | GET | 账户余额 |
| `/api/crypto/positions` | GET | 当前持仓 |
| `/api/crypto/orders` | GET | 订单列表 |
| `/api/crypto/signals` | GET | 交易信号 |
| `/api/crypto/indicators/{symbol}` | GET | 技术指标 |

### 3.2 API响应格式

```json
{
  "success": true,
  "data": {...},
  "timestamp": "2026-05-31T10:00:00Z"
}
```

---

## 4. 实现计划

### 4.1 阶段1：创建目录结构和移动代码

- [ ] 创建 `src/crypto/` 目录结构
- [ ] 复制crypto-hub的核心代码到新目录
- [ ] 更新导入路径

### 4.2 阶段2：创建API路由

- [ ] 创建 `src/api/routes_crypto.py`
- [ ] 注册路由到main.py
- [ ] 移除API代理代码

### 4.3 阶段3：更新配置

- [ ] 合并配置文件
- [ ] 更新环境变量

### 4.4 阶段4：测试和清理

- [ ] 运行测试
- [ ] 更新文档
- [ ] 停止crypto-hub服务

---

## 5. 风险评估

### 5.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 导入路径错误 | 高 | 仔细检查所有导入 |
| 配置冲突 | 中 | 统一配置管理 |
| 测试失败 | 中 | 逐步迁移，逐个测试 |

### 5.2 业务风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 功能丢失 | 高 | 完整测试所有功能 |
| 服务中断 | 中 | 先测试后切换 |

---

## 6. 总结

本设计文档描述了将加密货币模块合并到主服务的架构、API设计和实现计划。通过统一服务架构，可以简化部署、减少资源占用、提高代码可维护性。

预计总工时：2-3天
