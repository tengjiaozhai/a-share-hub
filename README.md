# A股自动交易系统

## 概述

基于多智能体LLM决策的A股自动交易系统，包含数据采集、特征工程、决策引擎、风险控制和执行网关。

## 架构

- **Linux研究节点**: 市场数据、LLM决策、回测、组合管理
- **Windows执行节点**: QMT/MiniQMT实盘执行

## 快速开始

1. 安装Python 3.11环境
2. 安装依赖：`pip install -e .`
3. 配置 `.env` 文件
4. 运行测试：`pytest tests/`

## 配置说明

系统通过环境变量或 `.env` 文件进行配置：

- `DATABASE_URL`: 数据库连接字符串
- `API_TOKEN`: API认证令牌
- `ENABLE_LIVE_TRADING`: 是否启用实盘交易（默认：false）
- `EXECUTION_MODE`: 执行模式（默认：shadow）
- `RUNTIME_STORE_PATH`: 运行时数据存储路径（默认：~/.a-share-hub/runtime_store）

## 模块说明

- `src/core/`: 核心配置和工具
- `src/data/`: 数据提供者
- `src/indicators/`: 技术指标
- `src/strategy/`: 策略逻辑
- `src/decision/`: 决策引擎
- `src/agents/`: LLM代理
- `src/portfolio/`: 组合管理
- `src/risk/`: 风险控制
- `src/execution/`: 执行引擎
- `windows_agent/`: Windows执行节点
