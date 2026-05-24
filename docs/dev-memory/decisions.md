# 技术决策

## 服务器配置要求

**决策日期**: 2026-05-23  
**状态**: 已确认

### 最低配置

- **CPU**: 2核（2核4GB可满足开发/测试）
- **内存**: 4GB（8GB推荐用于生产）
- **磁盘**: 20GB+
- **操作系统**: Linux（推荐Ubuntu或Amazon Linux）

### 当前配置

- **服务器**: AWS EC2 (13.214.201.113)
- **配置**: 2核4GB内存
- **区域**: ap-southeast-1 (新加坡)

### 决策依据

- 2核2GB服务器在安装依赖时CPU和内存耗尽
- 2核4GB可满足基本运行需求
- 后续可升级到t3.large (2核8GB) 用于生产

---

## Python环境管理

**决策日期**: 2026-05-23  
**状态**: 已确认

### 选择

使用Miniconda管理Python 3.11环境

### 配置

- **安装路径**: `/home/ec2-user/miniconda3`
- **环境名称**: `py311`
- **Python版本**: 3.11.15
- **调用方式**: `/home/ec2-user/miniconda3/envs/py311/bin/python`

### 决策依据

- 系统自带Python 3.9版本过低
- conda提供干净的环境隔离
- 使用完整路径避免conda自动激活的资源消耗

---

## 数据库选择

**决策日期**: 2026-05-23  
**状态**: 已确认

### 选择

PostgreSQL 15.16（AWS EC2上安装）

### 配置

- **主机**: localhost:5432
- **用户**: douya
- **密码**: douya
- **数据库**: douya

### 决策依据

- PostgreSQL 15.16功能完整
- 已配置md5认证支持密码登录
- 适合A股交易系统的数据存储需求

---

## 代码版本管理

**决策日期**: 2026-05-24  
**状态**: 已确认

### 选择

GitHub私有仓库 + SSH密钥认证

### 配置

- **仓库地址**: https://github.com/tengjiaozhai/a-share-hub
- **认证方式**: SSH密钥
- **同步分支**: master

### 同步流程

```bash
# 服务器推送
cd /home/ec2-user/a-share-hub
git add .
git commit -m "描述"
git push origin master

# 本地拉取
cd ~/workSpace/tranding/a-share-hub
git pull origin master
```

### 决策依据

- GitHub提供免费私有仓库
- SSH密钥比密码更安全
- 方便本地和服务器之间的代码同步
- 支持版本历史和协作

---

## 仪表盘方案

**决策日期**: 2026-05-24  
**状态**: 已确认

### 选择

自定义简单仪表盘（HTML + FastAPI）

### 文件位置

- **前端页面**: `src/api/dashboard.html`
- **后端路由**: `src/api/routes_dashboard.py`
- **访问地址**: http://13.214.201.113:8000/dashboard

### 功能

- 系统状态监控
- 资产总览
- 最近决策和订单
- 持仓明细

### 决策依据

- 无需额外依赖，快速实现
- 与现有FastAPI后端无缝集成
- 暗色主题，专业美观
- 后续可升级为Grafana或适配QuantDinger-Vue

---

## 项目目录结构

**决策日期**: 2026-05-23  
**状态**: 已确认

### 位置

`/home/ec2-user/a-share-hub`

### 结构

```
/home/ec2-user/a-share-hub/
├── src/
│   ├── core/           # 核心配置和工具
│   ├── data/           # 数据提供者
│   ├── indicators/     # 技术指标
│   ├── strategy/       # 策略逻辑
│   ├── decision/       # 决策引擎
│   ├── agents/         # LLM代理
│   ├── portfolio/      # 组合管理
│   ├── risk/           # 风险控制
│   ├── execution/      # 执行引擎
│   └── api/            # API路由（含仪表盘）
├── tests/              # 测试文件（65个测试）
├── windows_agent/      # Windows执行节点
├── scripts/            # 脚本文件
├── docs/               # 文档
└── artifacts/          # 阶段产物
```

### 决策依据

- 遵循阶段计划中的文件结构锁定
- 清晰的模块分离便于维护
- 支持后续的Windows执行节点集成
- 仪表盘文件放在api目录下，便于管理

---

## 影子模式

**决策日期**: 2026-05-24  
**状态**: 已确认

### 说明

影子模式 = 系统正常运行，但不真正下单

### 配置

```python
# .env 文件
ENABLE_LIVE_TRADING=false  # 实盘关闭
EXECUTION_MODE=shadow      # 影子模式
```

### 迁移路径

```
影子模式（当前）
    ↓ 验证2-4周
小资金实盘（1-3只股票，低仓位）
    ↓ 验证1-2周
正常实盘
```

### 决策依据

- 先用假钱跑，确认策略有效
- 测试系统没有bug
- 建立信任后再用真钱
- 符合监管要求（程序化交易先报告、后交易）
