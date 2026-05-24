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

## 影子模式

系统使用fail-closed影子模式脚本进行安全测试：

```bash
# 运行影子周期
./scripts/run_shadow_cycle.sh

# 运行对账
./scripts/run_reconcile.sh
```

所有脚本都遵循fail-closed原则：任何步骤失败都会导致整个脚本退出，确保问题不会被忽略。

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
