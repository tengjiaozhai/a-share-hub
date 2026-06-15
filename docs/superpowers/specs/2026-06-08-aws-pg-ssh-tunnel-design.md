# AWS PostgreSQL SSH Tunnel Acceleration Design

## Problem

当前真实运行链路的权威数据库在 AWS 新加坡，数据库访问延迟约 0.8s，直接影响：

- `dashboard` 首屏与轮询接口响应
- 自动模拟交易日频任务
- scheduler 启动期 backfill
- A 股 / 美股自选列表读写

现有代码里虽然大部分数据库访问已集中到 `Settings.database_url` 和 `src/storage/db.py`，但仍存在旁路直连：

- [src/a_stock/routes.py](/Users/shenmingjie/workSpace/tranding/a-share-hub/src/a_stock/routes.py)
- [src/us_stock/routes.py](/Users/shenmingjie/workSpace/tranding/a-share-hub/src/us_stock/routes.py)
- [scripts/init_a_share_watchlist.py](/Users/shenmingjie/workSpace/tranding/a-share-hub/scripts/init_a_share_watchlist.py)
- [scripts/init_us_watchlist.py](/Users/shenmingjie/workSpace/tranding/a-share-hub/scripts/init_us_watchlist.py)

这些路径绕开了统一的运行时连接治理，导致后续隧道方案即使落地，也可能出现“部分流量走隧道、部分流量仍直连”的不一致行为。

## Decision

采用方案 C：

- AWS PostgreSQL 继续作为唯一权威库
- 国内运行节点通过受管 SSH 隧道访问 AWS PostgreSQL
- 应用进程只连接本机数据库地址，不直接感知 AWS 主机地址

不采用：

- 阿里云 PostgreSQL 读副本
- 本地 SQLite 作为真实运行库
- 应用层 fallback 到 AWS 直连

## Goals

1. 让 `dashboard`、scheduler、自动模拟交易和 watchlist 操作都通过同一条低抖动链路访问权威库。
2. 保持 `DATABASE_URL` 作为唯一数据库连接权威入口。
3. 让隧道掉线时系统明确失败，而不是无声退化。
4. 让机器重启后隧道与应用都能自动恢复。

## Non-Goals

1. 不迁移数据库主库。
2. 不引入双写、双读、读副本或缓存掩盖数据库延迟。
3. 不改策略逻辑、账本模型或 dashboard 业务行为。
4. 不把 SSH 隧道逻辑嵌入 FastAPI 进程。

## Current Constraints

### 现有权威入口

- [src/core/config.py](/Users/shenmingjie/workSpace/tranding/a-share-hub/src/core/config.py) 定义 `database_url`
- [src/storage/db.py](/Users/shenmingjie/workSpace/tranding/a-share-hub/src/storage/db.py) 负责 SQLAlchemy engine 创建与 schema bootstrap
- [src/storage/dependencies.py](/Users/shenmingjie/workSpace/tranding/a-share-hub/src/storage/dependencies.py) 负责 `RuntimeStore` 实例化

### 现有旁路入口

- A 股 / 美股 watchlist routes 直接 `psycopg.connect(...)`
- watchlist 初始化脚本直接 `psycopg.connect(...)`

### 现有启动行为

- [src/main.py](/Users/shenmingjie/workSpace/tranding/a-share-hub/src/main.py) 启动时会注册 scheduler，并执行 startup backfill
- [src/api/routes_health.py](/Users/shenmingjie/workSpace/tranding/a-share-hub/src/api/routes_health.py) 当前只返回静态 `{"status": "ok"}`

这意味着如果数据库不可用，当前服务可能出现：

- `/health` 仍返回 `ok`
- 应用进程启动后，在真实业务路径里才暴露数据库问题
- 隧道是否连通没有统一检查点

## Target Architecture

### 运行结构

```text
FastAPI / Scheduler / Dashboard / Shadow Trading
            |
            v
DATABASE_URL=postgresql+psycopg://douya:***@127.0.0.1:15432/douya
            |
            v
systemd-managed ssh tunnel
            |
            v
AWS_HOST:127.0.0.1:5432
            |
            v
PostgreSQL douya
```

### 核心边界

1. 应用只看 `DATABASE_URL`。
2. `DATABASE_URL` 在真实运行节点必须指向本机 loopback 端口，例如 `127.0.0.1:15432`。
3. SSH 隧道由系统服务管理，不由 Python 进程启动。
4. A 股 / 美股 watchlist 的 `psycopg` 连接也必须从同一个 `DATABASE_URL` 派生。

## Component Design

### 1. 连接字符串收敛

新增一个存储层辅助模块，负责把 `DATABASE_URL` 解析为不同消费方需要的形式。

建议新文件：

- `src/storage/connection_url.py`

职责：

- 解析 `database_url`
- 生成给 `psycopg` 用的 DSN
- 验证真实运行时的 host 是否为本机 loopback
- 为运维检查脚本提供一致的端口解析

这样可以移除代码里散落的：

```python
database_url.replace("postgresql+psycopg://", "postgresql://")
```

### 2. Watchlist 连接收敛

保留现有 `AShareWatchlistStore` / `WatchlistStore` 的 `psycopg` CRUD 方式，但不再在 routes 和脚本里自己拼连接。

修改：

- `src/a_stock/routes.py`
- `src/us_stock/routes.py`
- `scripts/init_a_share_watchlist.py`
- `scripts/init_us_watchlist.py`

目标：

- 所有 `psycopg` 连接都经由统一 helper 构造
- 任何数据库地址切换，只改 `DATABASE_URL`

### 3. 受管 SSH 隧道

新增：

- `scripts/start_runtime_db_tunnel.sh`
- `deploy/systemd/a-share-hub-runtime-db-tunnel.service`

设计要求：

- `scripts/start_runtime_db_tunnel.sh` 负责读取 `.env` 或系统环境
- 从 `DATABASE_URL` 提取本地监听端口
- 使用现有 `AWS_HOST` / `AWS_SSH_USER` / `AWS_SSH_KEY_PATH`
- 固定转发：
  `LOCAL_PORT -> AWS_HOST:127.0.0.1:5432`
- 使用 `ssh -N -L ... -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3`
- 不依赖 `autossh`
- 由 `systemd Restart=always` 实现自动拉起

原因：

- plain `ssh` + `systemd` 已足够，依赖更少
- 隧道状态应由 OS 级守护，而不是应用代码管理

### 4. 运行时数据库健康检查

新增：

- `src/storage/health.py`
- `scripts/check_runtime_db.py`

职责：

- 执行 `select 1`
- 记录连接耗时
- 返回明确的成功 / 失败结果

用途：

- 启动前手工检查
- systemd `ExecStartPre`
- FastAPI readiness 接口复用

### 5. 区分 Liveness 与 Readiness

修改：

- `src/api/routes_health.py`

保留现有 `/health` 作为轻量 liveness。

新增 readiness 路径，例如：

- `GET /health/ready`

行为：

- 调用 runtime DB health probe
- 成功时返回 `200`
- 隧道断开或数据库不可达时返回 `503`
- 响应中包含 `latency_ms`

这样可以避免“进程活着但数据库链路已断”时误报健康。

### 6. 启动与运维流程

新增运行约束：

1. 隧道服务先启动
2. 数据库 readiness 成功
3. 再启动 API 服务

应用本身不做自动 fallback，不做自动拉起隧道，不在进程内重试 SSH。

## Runtime Flow

### 正常路径

1. `systemd` 启动 `a-share-hub-runtime-db-tunnel.service`
2. 隧道在本机暴露 `127.0.0.1:15432`
3. API / scheduler 通过 `DATABASE_URL` 连接本机端口
4. SQL 流量通过 SSH 隧道转发到 AWS PostgreSQL
5. `/health/ready` 返回 `ok + latency_ms`

### 失败路径

1. 隧道未建立：
   `check_runtime_db.py` 失败，readiness 返回 `503`
2. SSH 掉线：
   `systemd` 重启隧道服务；恢复前 readiness 持续 `503`
3. AWS PostgreSQL 不可用：
   隧道仍可能存在，但数据库 probe 失败；readiness 返回 `503`
4. `DATABASE_URL` 没有指向本机 loopback：
   helper 明确报错，阻止误配置直连国外数据库

## Security And Operations

1. SSH 私钥继续通过 `AWS_SSH_KEY_PATH` 指向本地文件，不进仓库。
2. 隧道只绑定 `127.0.0.1`，不对公网开放数据库端口。
3. 本方案不改变 PostgreSQL 用户、密码、schema 或迁移流程。
4. `.env.example` 需要更新为真实运行推荐值示例：
   `DATABASE_URL=postgresql+psycopg://douya:change_me@127.0.0.1:15432/douya`

## Rollout Plan

1. 先收敛连接入口，再引入隧道服务模板。
2. 本地或国内运行节点先验证 `check_runtime_db.py` 与 `ssh -L` 手工链路。
3. 再用 `systemd` 托管隧道。
4. 最后接入 readiness 和 README / runbook。

## Acceptance Criteria

### 功能

1. 真实运行节点上，`DATABASE_URL` 只指向 `127.0.0.1:<local_port>`。
2. A 股 / 美股 watchlist routes 与初始化脚本不再手写 `replace("postgresql+psycopg://", ...)`。
3. 存在一个受管 SSH 隧道启动脚本和一个 versioned `systemd` unit 模板。
4. 存在一个数据库 readiness 检查入口，能明确区分数据库可用与不可用。

### 行为

1. 隧道存在时，`select 1` 成功，返回连接耗时。
2. 隧道断开时，readiness 返回 `503`，而不是静默返回空数据。
3. AWS PostgreSQL 仍是唯一权威库，所有真实运行写入保持一致。

### 文档

1. README 明确说明真实运行推荐使用本机 loopback `DATABASE_URL`。
2. 新 runbook 说明隧道启动、验证、重启、排障。

## Verification

建议验收命令：

```bash
/opt/anaconda3/envs/py311/bin/python3 scripts/check_runtime_db.py
```

预期：

- 隧道正常时输出 `ok` 和连接耗时
- 隧道未建立时非零退出

```bash
curl -s http://127.0.0.1:8000/health/ready
```

预期：

- 正常时 `200`
- 隧道断开或数据库不可达时 `503`

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_config_env.py tests/test_health_api.py tests/test_a_stock_routes.py tests/test_us_stock_routes.py -q
```

预期：

- 新增和改动相关测试全部通过
