# 故障排除

## AWS 服务器缺少 psycopg3 导致 workbench 接口 500

**解决时间**: 2026-05-26  
**问题**: `GET /api/v1/dashboard/workbench` 返回 `Internal Server Error`，日志 `No module named 'psycopg'`

### 根本原因

`DATABASE_URL` 使用 `postgresql+psycopg://`（psycopg3 方言），服务器只装了 `psycopg2-binary`。

### 解决方案

```bash
~/miniconda3/envs/py311/bin/pip install psycopg[binary]
```

### 后续规则

- 部署新服务器时必须同时安装 `psycopg[binary]`（psycopg3）。
- `psycopg2-binary` 对应方言是 `postgresql+psycopg2://`，两者**不通用**。

---

## AWS 服务器旧进程缓存导致新代码不生效

**解决时间**: 2026-05-26  
**问题**: pip 安装新依赖后重启 uvicorn 仍然报 `ModuleNotFoundError`

### 根本原因

`killall python3` 只杀了部分进程，旧 uvicorn 子进程仍在运行，使用旧的进程内存。

### 可靠重启命令

```bash
ps aux | grep python | grep -v grep | awk '{print $2}' | xargs kill -9
sleep 3
nohup ~/miniconda3/envs/py311/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
```

---

## AWS 服务器缺少 httpx 导致 llm_client 导入失败

**解决时间**: 2026-05-26  
**问题**: uvicorn 启动失败，日志 `No module named 'httpx'`

### 解决方案

```bash
~/miniconda3/envs/py311/bin/pip install httpx
```

### 后续规则

`pyproject.toml` 的 `dependencies` 需显式列出 `httpx`，避免环境遗漏。

---

## SSH连接被拒绝

**解决时间**: 2026-05-23  
**问题**: SSH连接到远程服务器时提示"Permission denied"

### 原因

- 服务器配置为仅允许密码认证
- 需要使用sshpass工具传递密码

### 解决方案

```bash
sshpass -p '密码' ssh -o StrictHostKeyChecking=no root@服务器IP
```

---

## PostgreSQL连接失败

**解决时间**: 2026-05-23  
**问题**: 使用psql命令连接PostgreSQL时报错"command not found"

### 原因

- PostgreSQL客户端工具不在系统PATH中

### 解决方案

使用完整路径调用psql：

```bash
/www/server/pgsql/bin/psql -U douya -h localhost -d postgres
```

---

## conda Terms of Service错误

**解决时间**: 2026-05-23  
**问题**: 创建conda环境时报错"Terms of Service have not been accepted"

### 解决方案

```bash
/opt/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
/opt/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

---

## pyproject.toml构建后端错误

**解决时间**: 2026-05-23  
**问题**: pip安装时报错"Cannot import 'setuptools.backends._legacy'"

### 解决方案

使用正确的build-backend：

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"
```

---

## 服务器CPU/内存耗尽

**解决时间**: 2026-05-23  
**问题**: 安装依赖时服务器负载达到18+，CPU使用率85%+

### 解决方案

迁移到更高配置的服务器（AWS EC2 2核4GB）。

---

## GitHub SSH密钥认证失败

**解决时间**: 2026-05-24  
**问题**: git push时报错"Host key verification failed"

### 原因

- GitHub的主机密钥没有添加到known_hosts

### 解决方案

```bash
ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null
```

---

## GitHub API密码认证失败

**解决时间**: 2026-05-24  
**问题**: 使用GitHub API创建仓库时报错"Requires authentication"

### 原因

- GitHub已停止支持密码认证API操作
- 需要使用Personal Access Token或SSH密钥

### 解决方案

使用SSH密钥认证：
1. 在服务器上生成SSH密钥：`ssh-keygen -t rsa -b 4096`
2. 将公钥添加到GitHub：https://github.com/settings/keys
3. 使用SSH方式克隆和推送

---

## AWS安全组端口未开放

**解决时间**: 2026-05-24  
**问题**: 无法从外部访问仪表盘（端口8000）

### 原因

- AWS EC2的8000端口未从外部开放

### 临时解决方案

使用SSH隧道：
```bash
ssh -i /Users/shenmingjie/.ssh/xingxing.pem -L 8000:localhost:8000 ec2-user@13.214.201.113
# 浏览器访问: http://localhost:8000/dashboard
```

### 永久解决方案

在AWS控制台开放8000端口入站规则。

---

## uvicorn服务启动失败

**解决时间**: 2026-05-24  
**问题**: uvicorn服务启动后无法访问

### 原因

- 服务启动命令超时
- 可能是端口被占用

### 解决方案

```bash
# 杀死现有进程
pkill -f uvicorn

# 重新启动服务
cd /home/ec2-user/a-share-hub
nohup ~/miniconda3/envs/py311/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
```

---

## 行情数据源被三重封锁（2026-05-27）

**解决时间**: 2026-05-27  
**问题**: `GET /api/v1/market/quote?symbol=600519.SH` 返回 503，行情接口全部不可用

### 根本原因

三层封锁都不同：

| 源 | 问题 | 根因 |
|----|------|------|
| 东方财富 `push2.eastmoney.com` | HTTP 503 RemoteDisconnected | 代理规则拦截（REJECT,*.eastmoney.com） |
| 东方财富 `push2his.eastmoney.com` | HTTP 503 同上 | 同上（整个 eastmoney 族被封） |
| 新浪 `stock_zh_a_spot()` | JSON 解析失败 "Can not decode value starting with '<'" | 反爬虫返回 HTML（UA 检测 + IP 限制） |

### 为什么被封

**代理拦截东方财富原因**：
- 防爬虫：东方财富被大量量化框架滥用
- 防带宽：`push2.eastmoney.com` 是推送接口，易产生突发流量
- 防出口检测：代理为保护自身出口，拦截已知高风险域名

**新浪反爬原因**：
- 免费数据流量大：所有开源量化框架都用新浪
- 无差别反爬：检测到非浏览器 UA（akshare 库没设置 User-Agent）
- IP 段限制：同一 IP 短时间内多次请求直接返回反爬页

**腾讯为什么不被封**：
- 轻量级指标：非全量实时行情，请求量天然少
- 无 UA 检测：直接返回原始数据，不做 HTML 包装
- 容量大：腾讯讯号推送基础设施成熟

### 解决方案

**改用腾讯接口**（已实施）

```python
# src/data/providers/akshare_provider.py
def _fetch_tencent_quotes(symbols: list[str]) -> pd.DataFrame:
    """批量拉腾讯行情，symbols 格式 ['600519.SH', '000858.SZ']"""
    # https://qt.gtimg.cn/q=sh600519,sz000858
    # 返回: v_sh600519="...", v_sz000858="..."
    # 字段 ~ 分隔，稳定可靠
```

### 后续预防

1. **监控腾讯可用性**：定期 probe `/api/v1/market/quote`，若全部 503 则告警
2. **备选方案**：本地 CSV + 腾讯历史 K 线接口（需单独调研）
3. **付费方案**：Wind 或 Bloomberg 行情 API（若免费方案都被封）

### 学到的教训

- 不能依赖单一行情源，互联网环境反爬越来越严
- 代理软件拦截规则会定期更新，需主动检测
- 新浪虽然开放但反爬强度高，不适合量化系统长期使用
- 腾讯讯号推送接口轻量可靠，但字段解析需自研

---

## 扫描器与回测信号矛盾（2026-05-29）

**解决时间**: 2026-05-29  
**问题**: 扫描器推荐 BUY 的股票，回测说 HOLD，用户困惑

### 根本原因

两套系统用完全不同的因子：
- 扫描器：实时因子（涨跌幅/振幅/量比/换手率）
- 回测：历史因子（动量20/60、MA偏离、RSI）

单日暴涨的股票扫描器高分，但 60 天趋势弱的回测低分。

### 解决方案

采用"扫描器预筛 + 回测确认"流水线：
- 扫描器取 Top-N×3 BUY 候选
- `confirm_buy_candidates()` 用历史 K 线逐只确认
- 只展示两边都同意 BUY 的股票

---

## 目标仓位永不清理（2026-05-29）

**解决时间**: 2026-05-29  
**问题**: `active_target_count` 虚高，2 天前的仓位仍显示"活跃"

### 根本原因

`target_positions` 创建后从不标记过期，`list_active_target_positions()` 只查 `status=ACTIVE`，不检查 `expires_at`。

### 解决方案

- 查询时加 `expires_at > now` 过滤
- 新增 `deactivate_expired_targets()` 方法
- 每次运行模拟前自动清理过期目标

---

## 分页按钮不显示（2026-05-29）

**解决时间**: 2026-05-29  
**问题**: 底部标签数据超过 PAGE_SIZE 但不显示分页控件

### 根本原因

分页条件 `rows.length > PAGE_SIZE`，当数据恰好等于 PAGE_SIZE 时不触发（`15 > 15 = false`）。

### 解决方案

改为 `rows.length >= PAGE_SIZE`，同时 PAGE_SIZE 从 15 降为 10。

---

## 服务端偏好未加载（2026-05-29）

**解决时间**: 2026-05-29  
**问题**: 保存观察列表后刷新页面，配置恢复为默认值

### 根本原因

`renderConfig` 函数中缺少 `config.watchlist` 的赋值逻辑，编辑过程中意外删除。

### 解决方案

在 `renderConfig` 函数开头添加 `config.watchlist` 判断和赋值。

---

## dashboard.html FileNotFoundError（CWD 问题）

**解决时间**: 2026-06-01  
**问题**: `GET /dashboard` 返回 500，日志 `FileNotFoundError: 'src/api/dashboard.html'`

### 根本原因

uvicorn 用 `--app-dir` 启动时，进程 CWD 是 `/home/ec2-user`（nohup 父 shell 目录），而非项目根目录。代码里 `open("src/api/dashboard.html")` 用相对路径找不到文件。

### 解决方案

```python
# src/api/routes_dashboard.py
from pathlib import Path

@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    html_path = Path(__file__).parent / "dashboard.html"
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()
```

### 规则

**永远不要用相对路径读文件**。用 `Path(__file__).parent` 锚定到代码文件位置。

---

## StockCatalogCache 空结果缓存 24 小时

**解决时间**: 2026-06-01  
**问题**: 首次冷启动扫描返回 `no_catalog`，之后 24 小时内所有扫描一直返回 `no_catalog`

### 根本原因

`StockCatalogCache.load()` 中，fetcher 失败返回空 DataFrame 时，空结果仍被缓存 24 小时（`ttl_seconds=86400`）。后续 load 直接命中空缓存，永不重试。

### 解决方案

```python
# src/data/providers/akshare_catalog.py
def load(self, fetcher):
    ...
    frame = normalize_stock_list_frame(fetcher())
    if frame.empty:
        return frame  # 空结果不缓存，下次重试
    self._frame = frame
    self._expires_at = now + timedelta(seconds=self.ttl_seconds)
    return frame
```

同时在 `_build_catalog_frame()` 加 3 次重试（2s/4s 退避），扛住 SOCKS 隧道偶发 reset。

### 规则

**缓存层：失败结果不写缓存**。成功结果才缓存，失败留给下次重试。

---

## uvicorn 启动后 CWD 导致 .env 加载失败

**解决时间**: 2026-06-01  
**问题**: `GET /api/v1/dashboard/workbench` 返回 500，日志 `password authentication failed for user "app_user"`

### 根本原因

`config.py` 用 `env_file=".env"`（相对 CWD）。uvicorn CWD 是 `/home/ec2-user`，找不到项目根的 `.env`，走默认值 `app_user:change_me`。

### 解决方案

```python
# src/core/config.py
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
```

### 规则

**pydantic-settings 的 env_file 必须用绝对路径**。用 `Path(__file__).resolve().parents[N]` 锚定到项目根。

---

## 回测报错 "watchlist is empty"

**解决时间**: 2026-06-06  
**问题**: 前端点击"运行回测"，返回 `{"detail":"watchlist is empty"}`

### 根本原因

前端 `cfg-market` 默认值是 `"a"`（A股），但 watchlist 里是美股符号（MRVL, NVDA.US, AAPL）。后端用 A 股数据源拉美股 → 失败。

### 解决方案

后端自动检测 market（从 watchlist 符号推断）：

```python
market = "us" if any(s.upper().endswith(".US") for s in watchlist) else config.get("market", "a")
```

### 规则

**后端应对关键参数做 sanity check**。前端传的 market 参数不可靠，后端应从实际数据推断。

---

## MCP Tavily 连接失败（npx not found）

**解决时间**: 2026-06-06  
**问题**: opencode MCP Tavily 服务启动失败，`env: node: No such file or directory`

### 根本原因

opencode.json 中配置 `"command": ["npx", "-y", "tavily-mcp@0.1.4"]`。`npx` 依赖 nvm 的 PATH，但非交互 shell 不加载 nvm，导致 `npx` 找不到。

### 解决方案

1. 全局安装 tavily-mcp：`npm install -g tavily-mcp@0.1.4`
2. 用绝对路径替换 npx：

```json
"command": [
  "/Users/shenmingjie/.nvm/versions/node/v24.13.1/bin/node",
  "/Users/shenmingjie/.nvm/versions/node/v24.13.1/bin/tavily-mcp"
]
```

### 规则

**MCP 配置中不要用 `npx`/`uvx`/`python` 裸命令**。非交互 shell 不加载 nvm/conda，必须用绝对路径。

---

## AWS 新功能部署缺依赖（yfinance）

**解决时间**: 2026-06-06  
**问题**: 合并 feature 分支后 uvicorn 启动失败，`ModuleNotFoundError: No module named 'yfinance'`

### 根本原因

feature 分支新增了美股模块（`src/us_stock/yahoo_provider.py`），依赖 `yfinance` 和 `cachetools`，但 AWS 环境未安装。

### 解决方案

```bash
~/miniconda3/envs/py311/bin/pip install yfinance cachetools
```

### 规则

**合并新功能分支到 master 前，检查 pyproject.toml 是否新增了依赖**。部署时必须在 AWS 上安装新依赖。

---

## 数据库迁移生产事故：僵尸连接阻塞 DDL + 迁移不幂等（2026-06-20）

**事故时间**: 2026-06-20 凌晨
**触发动作**: 账户绑定改造迁移（`000013 → 000014 → 000015`）
**最终影响**: 三个迁移脚本都卡住 / 失败，需要手动终止连接 + 重写迁移

**配套插图**: `docs/dev-memory/assets/db-migration-incident.png`（左：僵尸连接占座；右：迁移脚本假设不存在的调料）

### 小白讲解（一句话版）

数据库迁移时同时出了两个互相叠加的问题：**老的进程占着数据库的桌子不让位**（僵尸连接）+ **迁移脚本按一份不存在的菜单找调料**（假设错误的索引）。两个问题叠加导致 DDL（修改表结构）完全跑不下去。

---

### 问题 1：僵尸连接阻塞 DDL（idle-in-transaction 锁表）

#### 什么是 idle-in-transaction？

数据库连接有两种状态：
- **事务里**：正在 `BEGIN ... COMMIT/ROLLBACK` 当中
- **事务外**：刚连上没开始任何事务

`idle in transaction` 是第三种反常状态：**已经 BEGIN 了，但啥也没干，连接静静地搁在那里**。它仍然持有事务锁。

#### 餐厅比喻

把数据库的每一行想成一张餐桌。每个 `BEGIN` 就是客人坐下并举起手（"我开始吃饭了"）。

- **正常情况**：客人点菜、吃饭、结账、离开 → 桌子释放
- **僵尸情况**：客人坐下举了手（`BEGIN`），然后被老板 `pkill -9` 干掉了 → 人走了但桌子还举着手，没人结账

更糟的是：**客人消失后，桌子上的餐具依然归他所有**。这就是"行锁"——其他客人想坐这张桌子，必须等僵尸"结账"（`COMMIT` 或 `ROLLBACK`）。

#### 为什么 `pkill -9` 会产生僵尸？

`kill -9` 是 SIGKILL，进程立刻死亡，没有机会执行任何清理逻辑：
- 没有 `COMMIT`
- 没有 `ROLLBACK`
- 没有关闭 socket

数据库服务端只能看到"客户端连接断开了，但事务还没结束"。在 PostgreSQL 默认配置下，这种僵尸事务**永远不会被清理**，直到你手动 `pg_terminate_backend()`。

#### 当时的现象

迁移 000013 跑到一半卡死，超时无响应。查 `pg_stat_activity`：

```
2218761 idle in transaction  ... SELECT ... FROM us_watchlist ...
2218758 idle in transaction  ... SELECT ... FROM a_share_watchlist ...
2223237 active               ... ALTER TABLE a_share_watchlist ADD COLUMN ...
2223336 active               ... ALTER TABLE a_share_watchlist ADD COLUMN ...
```

前面两个是僵尸连接（持锁的 SELECT 不释放），后面两个是排队的 ALTER TABLE（永远等不到锁）。

#### 修复（4 层防御）

| 层 | 文件 | 措施 |
|---|---|---|
| 1. 服务端 | `ALTER DATABASE douya SET ...` | `idle_in_transaction_session_timeout = '5min'` / `statement_timeout = '10min'` |
| 2. 客户端 | `src/storage/db.py` | `pool_recycle=1800` + `pool_reset_on_return=rollback` + connect event 设置 client 级超时 |
| 3. 应用 | `src/main.py` | FastAPI lifespan shutdown 显式 `engine.dispose()` |
| 4. 运维 | `scripts/db_cleanup_zombies.py` | cron 每 5 分钟清理一次僵尸 |

#### 给小白的规则

> **永远不要 `kill -9` 跑了 SQLAlchemy 的进程**。要么用 SIGTERM（`kill -15`）让进程优雅退出，要么用 systemd / FastAPI lifespan 接管关闭逻辑。如果必须用 `kill -9`，**事后立刻跑 zombie 清理脚本**。

---

### 问题 2：迁移脚本不幂等（假设不存在的索引）

#### 什么是幂等（idempotent）？

`f(x) = f(f(x))` — 跑一次和跑 N 次结果一样。

迁移幂等就是：**同一个迁移脚本连续跑两遍，第二遍应该是 no-op（不做任何事），不能报错**。

#### 当时的现象

迁移 000015 报：
```
sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedObject)
index "uq_paper_accounts_market_kind" does not exist
[SQL: DROP INDEX uq_paper_accounts_market_kind]
```

脚本要 `DROP INDEX uq_paper_accounts_market_kind`，但这个索引**根本不存在**。

#### 菜谱比喻

菜谱（迁移脚本）写：

> 步骤 5：把"特制酱油"瓶子从调料柜里拿出来丢掉（`DROP INDEX uq_paper_accounts_market_kind`）

但厨房里根本没有"特制酱油"——只有"普通酱油"。结果：厨师翻箱倒柜找不到，崩溃了。

#### 根因：迁移开发时假设了"理想 schema"

写迁移时，开发者按"应该有什么"写。但实际数据库可能是：
- 老版本部署，缺的索引
- 之前迁移失败半途而废
- 手工 `DROP` 过

**硬编码索引名 = 假设数据库已经处于某个状态**，这是迁移脚本的最大反模式。

#### 修复（5 个规则）

| 规则 | 示例 |
|---|---|
| 1. 用 `DROP INDEX IF EXISTS` 而不是 `op.drop_index()` | `op.execute("DROP INDEX IF EXISTS xxx")` |
| 2. 用 `DROP CONSTRAINT IF EXISTS` 而不是 `op.drop_constraint()` | `op.execute("ALTER TABLE xxx DROP CONSTRAINT IF EXISTS yyy")` |
| 3. 写入操作前先 `inspector.get_columns/tables/indexes()` 检查是否已存在 | `_column_exists(inspector, "xxx", "user_id")` |
| 4. 加 `nullable=False` 的列前必须先有 `server_default` | 否则老数据插入失败 |
| 5. 删 `server_default` 前先检查列是否还有 default | 否则第二次跑会因 default 已为 None 而抛错 |

#### 修复后的 000014 模板

```python
def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in _USER_TABLES:
        # 1) 检查列是否存在
        if not _column_exists(inspector, table, "user_id"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.add_column(
                    sa.Column("user_id", sa.String(64),
                              nullable=False, server_default="system")
                )
        # 2) 检查索引是否存在
        if not _index_exists(inspector, table, f"ix_{table}_user_id"):
            with op.batch_alter_table(table) as batch_op:
                batch_op.create_index(f"ix_{table}_user_id", ["user_id"])
        # 3) 拿掉 server_default 前检查还在不在
        if not is_sqlite and _column_has_default(inspector, table, "user_id"):
            op.alter_column(table, "user_id", server_default=None)
```

#### 给小白的规则

> **写 alembic 迁移时，默认假设"这是第二次跑"**。所有 `DROP` 加 `IF EXISTS`，所有 `CREATE` 前先 inspect。如果连不上 inspect，老老实实用 `IF NOT EXISTS`。

---

### 两个问题的关联

两个问题之所以叠加：
1. 僵尸连接持锁 → 迁移 000013 跑不下去
2. 修好 000013 后跑 000014 → 又卡在锁上
3. 杀完僵尸再跑 → 000015 又因不幂等挂了

**修复顺序**：先杀僵尸（解锁）→ 再修迁移（幂等）→ 再重启服务（带 dispose）→ 最后验证。

---

### 后续预防规则

1. **任何 alembic 迁移 PR 必须包含幂等性 review**：检查所有 DROP 是否带 IF EXISTS
2. **PostgreSQL 服务端 `idle_in_transaction_session_timeout = '5min'` 必须保留**（已应用到 `douya` 数据库）
3. **FastAPI lifespan 中必须 `engine.dispose()`**（已添加到 `_register_app_lifespan`）
4. **运维 cron 每 5 分钟跑 `db_cleanup_zombies.py`**（已创建脚本，待部署 cron）
5. **`pkill -9` 是核武器，只在最后才用**；首选 SIGTERM

---

### 经验教训（沉淀到 patterns.md）

这次产出的可重用模式：
- 多层防御（server → client → app → ops）的设计哲学
- 迁移幂等性的 5 条规则
- graceful shutdown 范式（lifespan.dispose）

详见 `patterns.md` 中的"数据库迁移防御层"小节。
