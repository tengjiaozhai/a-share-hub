# 技术决策

## LLM 接入方式

**决策日期**: 2026-05-26  
**状态**: 已确认

- `LLM_PROVIDER=mock` 或 `LLM_API_KEY` 为空时走 mock，否则调用真实接口。
- 真实调用使用 `httpx` 同步客户端，超时 30s，失败自动降级为 mock 输出（`action=HOLD, confidence=0`）。
- prompt 要求返回 JSON object，走 `response_format={"type":"json_object"}`，由 `parse_decision_output` 解析。
- 当前接入 DeepSeek，模型名称从 `settings.llm_model` 读取（`.env` 中配置）。

---

## 行情数据源接入方式

**决策日期**: 2026-05-26  
**状态**: 已确认

- 默认 `MARKET_DATA_PROVIDER=mock`，可切换为 `akshare`。
- `AkshareProvider` 在 `src/data/providers/akshare_provider.py`，实现 `DataProvider` 接口。
- 探针方式：`is_available()` 检查 `import akshare` 是否成功，无 token 依赖。
- 股票代码格式：`600519.SH`（上交所）/ `000001.SZ`（深交所），`_split()` 函数负责拆分。

---

## 服务探针规则

**决策日期**: 2026-05-26  
**状态**: 已确认

`GET /api/v1/dashboard/workbench` 的 `services` 字段规则：
- `database`: 始终 `ok`（数据库连通才能响应请求）。
- `llm`: `api_key` 已配置 → `ok`；provider=mock → `ok`；否则 `unknown`。不在探针里消耗 token。
- `market`: `akshare` 可导入 → `ok`；provider=mock → `ok`；否则 `error`。

---

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

---

## 行情数据源最终决策（2026-05-27 更新）

**决策日期**: 2026-05-27  
**状态**: 已确认  
**优先级**: 高（影响系统可用性）

### 技术决策

**行情数据源方案：腾讯 `qt.gtimg.cn` 作为主力方案**

- **库**：akshare (open-source)
- **接口**：`stock_zh_a_spot()` 走新浪，已弃用；改用自研 `_fetch_tencent_quotes()` 直接调腾讯原生接口
- **域名**：`https://qt.gtimg.cn/q=<symbol_list>`
- **返回格式**：`v_sh600519="..."` 格式（`~` 分隔字段）
- **缓存策略**：每个 code 独立 `SpotSnapshotCache` 实例，TTL 900s（15分钟）
- **轮询周期**：前端 `dashboard.html` 改为 15 分钟轮询一次

### 为什么选腾讯而非东方财富/新浪

| 源 | 拦截原因 | 状态 |
|----|---------|------|
| 东方财富 `push2.eastmoney.com` | 代理规则拦截（反爬 + 防滥用） | ❌ 不可用 |
| 东方财富 `push2his.eastmoney.com` | 同上，整个 `*.eastmoney.com` 被封 | ❌ 不可用 |
| 新浪 `sina.com` | 反爬虫（UA 检测 + IP 限制） | ❌ 不可用 |
| 腾讯 `qt.gtimg.cn` | 轻量指标、容量大、无 UA 检测 | ✅ 可用 |

### 技术细节

**字段映射**（腾讯返回的 `~` 分隔值）
```
[3]  = 最新价（close）
[4]  = 昨收（prev_close）
[5]  = 今开（open）
[6]  = 成交量（volume）
[33] = 最高（high）
[34] = 最低（low）
[37] = 成交额（amount）
```

**代码格式规范化**
```
腾讯 code: "sh600519" / "sz000858" / "bj920001"
标准 code: "600519" / "000858" / "920001"
symbol 格式: "600519.SH" / "000858.SZ" / "920001.BJ"
```

### 文件变更

- `src/data/providers/akshare_provider.py`：新增 `_fetch_tencent_quotes()` + 每 code 独立缓存
- `src/api/dashboard.html`：轮询间隔 `30000/10000`ms → `900000`ms（15分钟）
- `src/data/providers/akshare_snapshot_cache.py`：`get_row()` 支持 `code_col` 参数

### 回滚计划

若腾讯也被封：
1. 改用本地 CSV 股票列表 + 腾讯历史 K 线（需单独接口）
2. 引入 Playwright 浏览器自动化（模拟真实浏览）
3. 使用付费行情 API（Wind、Bloomberg）

---

## 代码架构规范化（2026-05-27 新增）

**决策日期**: 2026-05-27  
**状态**: 已确认

### AkshareProvider 的三层职责分离

1. **Catalog 层**（`StockCatalogCache`）：股票列表维护 + 搜索
   - TTL 缓存，减少重复查询
   - 仅支持 `/api/v1/market/stocks?query=...` 路由

2. **Snapshot 层**（`SpotSnapshotCache`）：行情快照 + 熔断
   - 独立实例制（每 code 一个），防止缓存互踩
   - 失败计数 + 熔断打开，避免级联故障

3. **错误分级**（`routes_market.py`）
   - `KeyError` → 404（symbol 不合法或不存在）
   - `AkshareUpstreamError` / `AkshareBreakerOpenError` → 503（上游不可用）

### 时区规范（已沉淀到 runtime_store.py）

所有 `created_at`、`expires_at` 在序列化时统一转 CST（UTC+8）
- 数据库里存的是 UTC 无时区时间
- 序列化层用 `_cst_iso()` 转换 + `+08:00` 标记
- 前端收到的全是 CST ISO 格式，无需转换
