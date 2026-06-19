# Scheduler Architecture Issues - 2026-06-19

**审查日期:** 2026-06-19  
**审查范围:** 后端日频调度、FastAPI 生命周期、启动 backfill、Dashboard 后台运行、前端刷新计时器  
**涉及模块:** `src/scheduler/daily_scheduler.py`, `src/main.py`, `src/paper_ledger/store.py`, `src/paper_ledger/backfill.py`, `src/api/routes_dashboard.py`, `src/api/dashboard_page/scripts/*`  
**状态:** 部分已处理，交易日历 MVP 已接入  
**结论:** 当前调度能力已完成 P0/P1 基础治理，并已接入第一版交易日历准入；仍不等于生产级实盘调度，还需要交易日历落库、外部日历同步和实盘执行前置 gate。

---

## 0. AI IDE 快速接手摘要

本节用于让其他 AI IDE 快速理解 `issue-fix` 分支当前已经达到的效果、实现边界和下一步入口。

### 0.1 当前分支与 worktree

```text
分支: issue-fix
独立 worktree: /Users/shenmingjie/workSpace/tranding/a-share-hub-issue-fix
原 master 目录: /Users/shenmingjie/workSpace/tranding/a-share-hub
```

`a-share-hub-issue-fix` 是独立 git worktree，可与原目录的 `master` 并行开发，避免两个 AI IDE 互相切分支。

### 0.2 本版已达到的效果

#### 调度基础治理

- `pyproject.toml` 已补充 `apscheduler` 依赖。
- `DailyScheduler` 使用 `AsyncIOScheduler(timezone=Asia/Shanghai)`。
- A 股 job 保持北京时间工作日 09:15 触发。
- 美股 job 保持北京时间工作日 21:15 触发。
- APScheduler job 已配置：
  - `max_instances=1`
  - `coalesce=True`
  - `misfire_grace_time=300`
- `_execute_daily_trading()` 未实现时会显式失败，不再把空实现误标为 `success`。
- `scheduled_job_locks` 调度锁已引入，用于防止多 worker / 多实例重复执行。
- 调度锁支持 `expires_at` 过期后重新抢占，避免进程 crash 后永久死锁。
- `check_run_exists()` 已从只检查 `success` 扩展为阻断 `running/success/skipped`，`failed` 默认允许重试。

#### 交易日历 MVP

已新增统一模块：

```text
src/market_calendar/
├── __init__.py
├── exceptions.py
├── models.py
├── service.py
└── static_calendars.py
```

已实现：

- `MarketSession` 领域模型。
- `TradingCalendarService` 统一服务入口。
- A 股 / 美股周末判断。
- A 股 / 美股静态节假日判断。
- `previous_trading_day()`。
- `next_trading_day()`。
- `recent_trading_days()`。
- `next_trading_run_at()`。
- `UnsupportedMarketError` fail-fast。

#### Scheduler 接入效果

`src/scheduler/daily_scheduler.py` 已接入 `TradingCalendarService`：

```text
cron 触发
↓
抢 daily_trading:{market}:{date} 调度锁
↓
检查已有 running/success/skipped auto run
↓
判断交易日
↓
非交易日: 创建 auto run，状态 skipped，写入 reason，不进入交易逻辑
↓
交易日: 创建 running run，进入 _execute_daily_trading()
```

非交易日现在是“主动跳过”，不是失败：

```text
run.status = skipped
lock.status = skipped
run.error_message = calendar reason
```

#### Backfill 接入效果

`src/paper_ledger/backfill.py` 已从“最近 N 个自然日”切换为“最近 N 个交易日”：

```text
calendar.recent_trading_days(market, today, days)
```

效果：

- 周末不会生成 backfill nav。
- 静态节假日不会生成 backfill nav。
- `days=30` 语义变为最近 30 个交易日。
- run params 中记录：`calendar_mode=trading_days`。

#### Dashboard 接入效果

`src/api/routes_dashboard.py` 的 automation payload 已扩展：

```json
{
  "today_status": "skipped",
  "last_run_at": "...",
  "next_run_at": "...",
  "next_cron_at": "...",
  "next_trading_run_at": "...",
  "next_trading_day": "...",
  "calendar_reason": "..."
}
```

语义：

- `next_cron_at`: APScheduler 下一次 cron 叫醒时间。
- `next_trading_run_at`: 下一个真实交易日运行时间。
- `calendar_reason`: 非交易日 skipped 的原因。

### 0.3 本版涉及的主要文件

```text
pyproject.toml
src/core/config.py
src/main.py
src/market_calendar/__init__.py
src/market_calendar/exceptions.py
src/market_calendar/models.py
src/market_calendar/service.py
src/market_calendar/static_calendars.py
src/paper_ledger/backfill.py
src/paper_ledger/models.py
src/paper_ledger/store.py
src/scheduler/daily_scheduler.py
src/api/routes_dashboard.py
alembic/versions/20260619_000011_add_scheduler_locks_and_paper_uniques.py
tests/test_market_calendar.py
tests/test_daily_scheduler.py
tests/test_paper_ledger_backfill.py
tests/test_paper_ledger_store.py
tests/test_dashboard_performance.py
```

### 0.4 已验收通过的测试

已通过核心验收：

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest \
  tests/test_market_calendar.py \
  tests/test_daily_scheduler.py \
  tests/test_paper_ledger_backfill.py \
  tests/test_paper_ledger_store.py \
  tests/test_dashboard_performance.py \
  -q
```

结果：

```text
36 passed
```

单项结果：

```text
tests/test_market_calendar.py        8 passed
tests/test_daily_scheduler.py        7 passed
tests/test_paper_ledger_backfill.py  5 passed
tests/test_paper_ledger_store.py     included in core suite
tests/test_dashboard_performance.py  included in core suite
```

另跑过：

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_page_contract.py -q
```

其中 `tests/test_dashboard_api.py` 通过；`tests/test_dashboard_page_contract.py::test_dashboard_route_uses_rendered_split_html` 因测试直接连接默认 PostgreSQL `127.0.0.1:5432`，本地 PG 未启动而失败，错误是 `connection refused`，不是交易日历逻辑导致。

### 0.5 当前仍未完成的边界

本版是交易日历 MVP，不包含：

- 未新增 `market_sessions` 落库表。
- 未做外部交易所日历同步。
- 未接 AkShare / NYSE calendar provider。
- 未精确处理美股提前收盘。
- 未做实盘订单提交前 calendar gate。
- 未动态调整 APScheduler job 注册时间。
- 静态节假日表需要后续补全年份并建立维护流程。

### 0.6 下一个 AI IDE 建议继续做什么

建议优先顺序：

1. 补全 / 校验 A 股和美股静态节假日表。
2. 修复 Dashboard page contract 测试对默认 PG 的依赖，使其走 SQLite fixture 或依赖覆盖。
3. 为 `market_calendar` 增加 runbook，说明如何维护节假日和 skipped 状态。
4. 后续再设计 `market_sessions` 落库与外部同步，不要在当前 MVP 内强行引入复杂 provider 链。

---

## 1. 背景

项目当前已具备基础自动触发能力：

- APScheduler 在 FastAPI lifespan 中启动。
- A 股日频任务：工作日 09:15。
- 美股日频任务：工作日 21:15。
- 服务启动时执行 auto 账户最近 30 天 backfill 检查。
- Dashboard 手动运行通过 FastAPI `BackgroundTasks` 后台执行。
- 前端通过 `setInterval` 刷新行情和仪表盘，通过 `setTimeout` 做 SSE 心跳/硬超时保护。

这些能力可以支撑本地开发和功能演示，但在真实部署、自动交易、长时间运行场景下存在调度治理缺口。

---

## 2. 问题汇总

| 优先级 | Issue | 类型 | 影响 |
|---|---|---|---|
| P0 | `apscheduler` 未声明依赖 | 依赖完整性 | 新环境可能无法启动服务 |
| P0 | 核心日频执行函数为空却可能标记 success | 状态正确性 | 误导 Dashboard 和后续风控/复盘 |
| P1 | CronTrigger 未显式设置时区 | 时间正确性 | 服务器时区变化会导致触发时间漂移 |
| P1 | Scheduler 挂在 Web 进程生命周期内 | 部署架构 | 多 worker / 多副本会重复执行 |
| P1 | 缺少分布式锁和唯一约束 | 幂等性 | 同一市场同一交易日 auto run 可重复创建 |
| P1 | `check_run_exists()` 只检查 success | 并发安全 | 两个 running 可同时创建，success 前无法拦截重复 |
| P1 | APScheduler job 缺少运行策略参数 | 调度稳定性 | 任务重入、misfire、补跑行为不可控 |
| P2 | 未接入交易日历 | 业务正确性 | 节假日、休市日、提前收盘日仍可能触发 |
| P2 | 启动 backfill 缺少互斥保护 | 启动幂等性 | 多实例启动可能重复补数据 |
| P2 | Dashboard BackgroundTasks 缺少直接调用保护 | 健壮性 | 单测或内部直接调用时可能 NoneType 报错 |

---

## 3. 详细 Issues

### Issue #1: `apscheduler` 依赖未写入 `pyproject.toml`

**优先级:** P0  
**类型:** 依赖完整性 / 启动阻断  
**发现位置:**

- `src/scheduler/daily_scheduler.py`
- `pyproject.toml`

**当前代码:**

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
```

但 `pyproject.toml` 的 `[project].dependencies` 未声明 `apscheduler`。

**影响:**

新环境只执行：

```bash
pip install -e .
```

随后启动服务时可能出现：

```text
ModuleNotFoundError: No module named 'apscheduler'
```

**建议方案:**

在 `pyproject.toml` dependencies 中补充：

```toml
"apscheduler>=3.10.0",
```

**验收标准:**

- [ ] `pyproject.toml` 声明 `apscheduler`。
- [ ] 全新虚拟环境 `pip install -e .` 后可以 import `src.scheduler.daily_scheduler`。
- [ ] `tests/test_daily_scheduler.py` 通过。

---

### Issue #2: `_execute_daily_trading()` 为空实现但任务可标记 success

**优先级:** P0  
**类型:** 状态正确性 / 业务风险  
**发现位置:** `src/scheduler/daily_scheduler.py`

**当前行为:**

```python
async def _execute_daily_trading(self, store, account_id, run_id, market):
    # TODO: 实现实际的交易逻辑
    pass
```

上层执行后仍会：

```python
store.update_run_status(run.run_id, "success")
```

**影响:**

定时任务可能产生如下错误事实：

- 没有获取行情。
- 没有运行决策。
- 没有生成目标仓位。
- 没有模拟成交。
- 没有更新持仓和净值。
- 但 run 状态为 `success`。

这会误导 Dashboard、复盘、风控和后续自动化判断。

**建议方案 A（推荐，未接真实逻辑前）:**

未实现前明确失败：

```python
raise NotImplementedError("daily trading execution is not implemented")
```

并让 run 进入 `failed`，避免误报成功。

**建议方案 B:**

引入 `skipped` / `noop` / `not_implemented` 状态，Dashboard 明确展示“调度触发成功，但交易执行未启用”。

**验收标准:**

- [ ] 空实现不会被标记为 `success`。
- [ ] Dashboard 能区分 `success`、`failed`、`skipped/noop`。
- [ ] 测试覆盖“执行函数未实现时 run 不应 success”。

---

### Issue #3: CronTrigger 未显式设置时区

**优先级:** P1  
**类型:** 时间正确性  
**发现位置:** `src/scheduler/daily_scheduler.py`

**当前代码:**

```python
CronTrigger(day_of_week="mon-fri", hour=9, minute=15)
CronTrigger(day_of_week="mon-fri", hour=21, minute=15)
```

注释说明美股任务为北京时间 21:15，但代码没有设置 `Asia/Shanghai`。

**影响:**

如果服务器时区不是北京时间，触发时间会漂移。多环境部署时尤其危险，例如：

- 本地 Mac 是北京时间。
- 云服务器是 UTC。
- Docker 镜像默认 UTC。

**建议方案:**

显式指定时区：

```python
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")

CronTrigger(
    day_of_week="mon-fri",
    hour=9,
    minute=15,
    timezone=CN_TZ,
)
```

美股任务同理。

**验收标准:**

- [ ] A 股、美股 CronTrigger 均显式使用 `Asia/Shanghai`。
- [ ] 测试验证 job trigger timezone。
- [ ] Dashboard 的 next_run_at 与预期北京时间一致。

---

### Issue #4: Scheduler 挂在 Web 进程生命周期内，存在多实例重复执行风险

**优先级:** P1  
**类型:** 部署架构 / 调度治理  
**发现位置:** `src/main.py`

**当前代码:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = get_scheduler()
    scheduler.start()
    try:
        _run_startup_backfill()
        yield
    finally:
        scheduler.stop()
```

**问题:**

Web 进程一启动就启动 scheduler。

如果使用：

```bash
uvicorn src.main:app --workers 4
```

则会启动 4 个 scheduler。若部署多台机器或多容器，也会重复启动 scheduler。

**影响:**

同一个 09:15 / 21:15 任务可被多个进程同时触发，导致重复创建 run、重复交易、重复写净值。

**建议方案:**

短期：增加配置开关。

```python
enable_scheduler: bool = False
app_role: str = "web"  # web / scheduler
```

仅当 `enable_scheduler=True` 或 `app_role=scheduler` 时启动 scheduler。

中期：拆出独立 scheduler 入口：

```bash
python -m src.main serve      # 只跑 Web
python -m src.main scheduler  # 只跑调度器
```

长期：调度服务独立部署，并通过数据库锁保证单实例执行。

**验收标准:**

- [ ] Web 进程可在不启动 scheduler 的情况下运行。
- [ ] Scheduler 可作为独立角色启动。
- [ ] 多 Web worker 不会创建多个 APScheduler 实例。
- [ ] README / runbook 明确部署方式。

---

### Issue #5: 缺少分布式锁和数据库唯一约束，无法保证幂等

**优先级:** P1  
**类型:** 幂等性 / 并发安全  
**发现位置:**

- `src/scheduler/daily_scheduler.py`
- `src/paper_ledger/store.py`
- `src/paper_ledger/models.py`

**当前逻辑:**

```python
if store.check_run_exists(market, today, "auto"):
    return

run = store.create_run(... run_source="auto" ...)
```

`check_run_exists()` 不是原子操作。并发情况下两个进程可以同时判断不存在，然后同时创建 run。

**影响:**

- 同一市场、同一交易日、同一 run_source 可能创建多条 run。
- 自动交易可重复执行。
- 净值、成交、持仓可能重复写入。

**建议方案:**

第一层：数据库唯一约束。

```text
paper_runs(market, trade_date, run_source) unique
```

第二层：引入调度锁表。

```text
scheduled_job_locks
- job_name
- market
- trade_date
- status
- locked_by
- locked_at
- expires_at
- finished_at
- error_message
```

执行前先抢锁：

```text
抢锁成功 → 执行
抢锁失败 → 跳过
```

**验收标准:**

- [ ] 并发触发同一 job 时只有一个 run 被创建。
- [ ] 数据库层有唯一约束兜底。
- [ ] 锁过期策略明确，避免死锁。
- [ ] 测试覆盖两个并发调度触发场景。

---

### Issue #6: `check_run_exists()` 只检查 success，无法阻止 running 重复

**优先级:** P1  
**类型:** 并发安全 / 状态语义  
**发现位置:** `src/paper_ledger/store.py`

**当前代码:**

```python
PaperRunRow.status == "success"
```

**问题:**

如果已有同日 `running` 任务，第二次触发仍会认为“不存在”。

**建议方案:**

短期：存在性判断至少包含：

```text
running
success
```

更合理的状态模型：

```text
accepted / running / success / failed / skipped / cancelled
```

定时任务防重复时，应阻止 `accepted/running/success` 重复创建。

**验收标准:**

- [ ] 同日已有 `running` auto run 时，新触发应跳过。
- [ ] 同日已有 `success` auto run 时，新触发应跳过。
- [ ] 同日已有 `failed` 是否允许重跑由策略明确决定。

---

### Issue #7: APScheduler job 缺少 `max_instances` / `coalesce` / `misfire_grace_time`

**优先级:** P1  
**类型:** 调度稳定性  
**发现位置:** `src/scheduler/daily_scheduler.py`

**当前 add_job:**

```python
self._scheduler.add_job(
    self._run_a_share_job,
    CronTrigger(...),
    id="a_share_daily",
    name="A股日频模拟交易",
)
```

**风险:**

- 上一次任务没跑完，下一次任务可能重入。
- 服务停机错过任务后，恢复时的补跑行为不清晰。
- 短时间堆积多个 missed jobs 时可能连续执行。

**建议方案:**

```python
self._scheduler.add_job(
    self._run_a_share_job,
    CronTrigger(...),
    id="a_share_daily",
    name="A股日频模拟交易",
    max_instances=1,
    coalesce=True,
    misfire_grace_time=300,
)
```

**参数语义:**

- `max_instances=1`: 同一个 job 只允许一个实例运行。
- `coalesce=True`: 错过多次触发时合并为一次。
- `misfire_grace_time=300`: 错过 5 分钟内可补跑，超过跳过。

**验收标准:**

- [ ] 两个日频 job 均配置上述调度策略。
- [ ] 测试验证 job 配置。
- [ ] 文档说明 misfire 策略。

---

### Issue #8: 未接入交易日历，休市日仍可能运行

**优先级:** P2  
**类型:** 业务正确性  
**发现位置:** `src/scheduler/daily_scheduler.py`

**当前逻辑:**

```python
CronTrigger(day_of_week="mon-fri", ...)
```

**问题:**

交易日不等于周一到周五。

A 股：

- 春节、国庆、清明、端午、中秋等节假日休市。
- 可能存在调休但市场不交易。

美股：

- 美国节假日休市。
- 可能提前收盘。
- 夏令时会影响与北京时间的对应关系。

**建议方案:**

Cron 仍可 daily 触发，但执行前必须判断：

```python
if not trading_calendar.is_trading_day(market, today):
    mark_skipped(...)
    return
```

A 股和美股使用各自交易日历。

**验收标准:**

- [ ] A 股法定休市日不执行交易逻辑。
- [ ] 美股休市日不执行交易逻辑。
- [ ] 休市日 run 状态为 `skipped`，而不是 `success`。
- [ ] Dashboard 能展示 skipped 原因。

---

### Issue #9: 启动 backfill 缺少互斥保护

**优先级:** P2  
**类型:** 启动幂等性 / 数据一致性  
**发现位置:**

- `src/main.py`
- `src/paper_ledger/backfill.py`

**当前逻辑:**

```python
if needs_backfill(store, market):
    backfill_recent_days(store, market, days=30)
```

`needs_backfill()` 判断是否已有任意成功 backfill run。多实例同时启动时可能同时判断需要 backfill。

**影响:**

- 重复创建 backfill run。
- 重复生成 nav snapshot。
- Dashboard 曲线可能出现重复或不一致。

**建议方案:**

- backfill 也走统一 job lock。
- `paper_nav_daily(account_id, trade_date, source)` 增加唯一约束。
- backfill 写入改为 upsert 或先锁定日期范围。

**验收标准:**

- [ ] 多实例同时启动不会重复 backfill。
- [ ] 同一 account/date/source 只有一条 nav snapshot。
- [ ] backfill 可重复调用且幂等。

---

### Issue #10: Dashboard `BackgroundTasks` 参数默认 None，直接调用不安全

**优先级:** P2  
**类型:** 健壮性 / 可测试性  
**发现位置:** `src/api/routes_dashboard.py`

**当前代码:**

```python
background_tasks: BackgroundTasks = None
...
background_tasks.add_task(_launch_dashboard_run, run_context_id, payload)
```

FastAPI 正常请求注入时可用，但单测或内部直接调用函数时可能出现：

```text
AttributeError: 'NoneType' object has no attribute 'add_task'
```

**建议方案:**

改为必填注入参数，或增加保护：

```python
if background_tasks is None:
    _launch_dashboard_run(run_context_id, payload)
else:
    background_tasks.add_task(_launch_dashboard_run, run_context_id, payload)
```

**验收标准:**

- [ ] FastAPI 请求路径仍异步后台执行。
- [ ] 直接函数调用不会 NoneType 报错。
- [ ] 测试覆盖 direct call。

---

## 4. 建议整改路线

### Phase 1: 最小安全修复

目标：避免新环境无法启动，避免未实现逻辑误报成功。

- [ ] `pyproject.toml` 增加 `apscheduler`。
- [ ] `_execute_daily_trading()` 未实现前不允许标记 `success`。
- [ ] `CronTrigger` 增加 `Asia/Shanghai` 时区。
- [ ] `add_job` 增加 `max_instances=1`, `coalesce=True`, `misfire_grace_time=300`。

### Phase 2: 幂等和并发保护

目标：防止多进程、多实例重复执行。

- [ ] 新增调度锁表或 job lock store。
- [ ] `paper_runs` 增加 `(market, trade_date, run_source)` 唯一约束。
- [ ] `paper_nav_daily` 增加 `(account_id, trade_date, source)` 唯一约束。
- [ ] `check_run_exists()` 调整为识别 `running/success`。
- [ ] 并发测试覆盖重复触发。

### Phase 3: 调度进程与 Web 进程解耦

目标：Web 扩容不影响 scheduler 单实例语义。

- [ ] 增加 `enable_scheduler` / `app_role` 配置。
- [ ] 新增 CLI 子命令 `scheduler`。
- [ ] Web 默认不启动 scheduler。
- [ ] runbook 说明部署方式。

### Phase 4: 交易日历和业务语义完善

目标：避免休市日误跑，明确 skipped 状态。

- [ ] 接入 A 股交易日历。
- [ ] 接入美股交易日历。
- [ ] 休市日标记 `skipped`。
- [ ] Dashboard 展示 skipped 原因。

---

## 5. 推荐目标架构

```text
Web Process
  ├── FastAPI API
  ├── Dashboard
  └── SSE stream

Scheduler Process
  ├── APScheduler
  ├── Job lock acquisition
  ├── Trading calendar check
  ├── Daily trading orchestration
  └── Paper ledger writes

Database
  ├── paper_runs unique(market, trade_date, run_source)
  ├── paper_nav_daily unique(account_id, trade_date, source)
  └── scheduled_job_locks
```

关键原则：

```text
Web 可以多副本；Scheduler 必须单语义。
数据库必须兜底幂等；应用层锁只是第一层保护。
定时触发不等于可以交易，必须经过交易日历和风控门。
未执行业务逻辑不能标记 success。
```

---

## 6. 验收总标准

完成整改后，应满足：

- [ ] 新环境安装依赖后 scheduler 模块可正常 import。
- [ ] 多 Web worker 不会导致多个 scheduler 同时执行同一日频任务。
- [ ] 同一市场、同一交易日、同一 run_source 最多只有一个有效 run。
- [ ] 未实现或执行失败的任务不会标记为 `success`。
- [ ] Cron 触发时间明确固定在北京时间。
- [ ] 休市日不会执行交易逻辑。
- [ ] Dashboard 能正确展示 `success / failed / skipped / running` 等状态。
- [ ] 单测覆盖 scheduler 注册、时区、幂等、防重复、未实现执行逻辑。
