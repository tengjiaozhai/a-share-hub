# 交易日历接入实施计划

**日期:** 2026-06-19  
**分支:** `issue-fix`  
**worktree:** `a-share-hub-issue-fix`  
**状态:** 待实施  
**目标:** 将当前“按 cron 时间触发”的自动交易调度，升级为“按交易市场规则执行”的调度体系。

---

## 1. 背景

当前项目已有日频调度能力：

- A 股 auto 任务：工作日 09:15，北京时间。
- 美股 auto 任务：工作日 21:15，北京时间。
- APScheduler 已显式使用 `Asia/Shanghai`。
- 已引入调度锁，避免多 worker / 多实例重复执行。
- 未实现的日频交易逻辑不再误标 `success`。

但目前调度仍然只基于 `mon-fri`，并不知道真实市场是否交易。

这会导致：

- A 股节假日仍可能触发任务。
- 美股节假日仍可能触发任务。
- backfill 按自然日补数据，可能生成周末/节假日净值。
- Dashboard 的 `next_run_at` 只能表示下一次 cron 时间，不等于下一次真实交易日运行时间。
- 后续接实盘时，非交易日或非交易时段缺少统一安全闸。

---

## 2. 设计原则

### 2.1 单一权威入口

所有交易日判断必须通过统一服务：

```text
TradingCalendarService
```

禁止在 scheduler、backfill、Dashboard、execution 各自散落 `weekday()`、节假日 hardcode 或临时判断。

### 2.2 Cron 只负责叫醒，交易日历负责准入

APScheduler 继续负责固定时间触发。

交易日历负责判断：

```text
今天是否交易日？
是否应该执行交易逻辑？
如果不执行，原因是什么？
下一个真实交易日是哪天？
最近 N 个交易日是哪几天？
```

不要把 APScheduler 改成动态按交易日注册 job。第一版保持简单。

### 2.3 休市日是 skipped，不是 failed

休市日主动跳过是正常业务状态，应记录为：

```text
skipped
```

不能标记为 `failed`，也不能假装 `success`。

### 2.4 第一阶段不依赖外部服务

MVP 先支持：

- 周末判断。
- 静态节假日表。
- A 股 / 美股基础交易时段。

后续再接入 AkShare、交易所日历或数据库缓存。

---

## 3. 目标架构

```text
APScheduler
  ↓
DailyScheduler
  ↓
TradingCalendarService
  ↓
MarketSession
  ↓
PaperLedgerStore / Dashboard / Backfill / Execution Gate
```

模块职责：

```text
src/scheduler/          负责触发和任务编排
src/market_calendar/    负责交易日历和市场 session 语义
src/paper_ledger/       负责 run/nav/fill/position 事实记录
src/api/routes_dashboard.py 负责状态展示
src/execution/          后续实盘或模拟执行前置 gate
```

---

## 4. 模块拆分

### 模块 A：`src/market_calendar/models.py`

职责：定义交易日历领域模型。

建议模型：

```python
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class MarketSession:
    market: str
    trade_date: date
    is_trading_day: bool
    open_at: datetime | None = None
    close_at: datetime | None = None
    is_early_close: bool = False
    reason: str | None = None
```

#### 任务 A1：新增 `MarketSession`

**任务内容:**

- 新增 `src/market_calendar/models.py`。
- 定义不可变 dataclass `MarketSession`。
- 字段覆盖 market、trade_date、is_trading_day、open_at、close_at、is_early_close、reason。

**成功标准:**

- [ ] `MarketSession` 可被 scheduler、backfill、Dashboard import。
- [ ] 非交易日 session 可表达 `reason`。
- [ ] 交易日 session 可表达开盘/收盘时间。
- [ ] 单测覆盖交易日与非交易日两种实例。

---

### 模块 B：`src/market_calendar/static_calendars.py`

职责：提供第一版静态节假日和基础交易时段。

建议内容：

```python
A_SHARE_HOLIDAYS = {
    "2026-01-01": "元旦休市",
}

US_HOLIDAYS = {
    "2026-01-01": "New Year's Day",
}

MARKET_TIMEZONES = {
    "a": "Asia/Shanghai",
    "us": "America/New_York",
}
```

#### 任务 B1：新增静态节假日表

**任务内容:**

- 新增 `A_SHARE_HOLIDAYS`。
- 新增 `US_HOLIDAYS`。
- 每个日期 value 存放休市原因。
- 第一版至少覆盖当前年份关键休市日，后续可补全。

**成功标准:**

- [ ] A 股周中节假日可识别为非交易日。
- [ ] 美股周中节假日可识别为非交易日。
- [ ] 休市原因可透传到 `MarketSession.reason`。
- [ ] 不在静态表且非周末的日期默认按交易日处理。

#### 任务 B2：新增市场时区和基础交易时段

**任务内容:**

- A 股时区：`Asia/Shanghai`。
- 美股时区：`America/New_York`。
- A 股默认交易时段：09:30 - 15:00。
- 美股默认交易时段：09:30 - 16:00。

**成功标准:**

- [ ] A 股交易日 session 返回北京时间开盘/收盘。
- [ ] 美股交易日 session 返回美东时间开盘/收盘。
- [ ] 单测验证 timezone 信息不丢失。

---

### 模块 C：`src/market_calendar/service.py`

职责：提供统一交易日历服务，其他模块只依赖此服务。

建议接口：

```python
class TradingCalendarService:
    def get_session(self, market: str, trade_date: date) -> MarketSession: ...
    def is_trading_day(self, market: str, trade_date: date) -> bool: ...
    def previous_trading_day(self, market: str, trade_date: date) -> date: ...
    def next_trading_day(self, market: str, trade_date: date) -> date: ...
    def recent_trading_days(self, market: str, end_date: date, count: int) -> list[date]: ...
    def should_run_daily_job(self, market: str, now: datetime) -> tuple[bool, str | None]: ...
```

#### 任务 C1：实现 `get_session()`

**任务内容:**

- 输入 market 和 trade_date。
- 判断 market 是否支持：`a` / `us`。
- 周末返回非交易日。
- 静态节假日返回非交易日，并附带 reason。
- 普通工作日返回交易日 session。

**成功标准:**

- [ ] 周六、周日返回 `is_trading_day=False`。
- [ ] A 股静态节假日返回 `is_trading_day=False` 且有中文 reason。
- [ ] 美股静态节假日返回 `is_trading_day=False` 且有英文/可读 reason。
- [ ] 普通交易日返回 `is_trading_day=True`。
- [ ] 不支持的 market fail fast，抛出明确异常。

#### 任务 C2：实现 `is_trading_day()`

**任务内容:**

- 调用 `get_session()`。
- 返回 bool。

**成功标准:**

- [ ] 行为与 `get_session().is_trading_day` 完全一致。
- [ ] 单测覆盖 A 股、美股、周末、节假日。

#### 任务 C3：实现 `previous_trading_day()` 和 `next_trading_day()`

**任务内容:**

- 从输入日期向前/向后遍历。
- 跳过周末和静态节假日。
- 返回最近有效交易日。

**成功标准:**

- [ ] 周五的下一交易日跳到下周一。
- [ ] 节假日前后的下一交易日正确跳过休市区间。
- [ ] 周一的上一交易日可跳过周末。
- [ ] 遍历有最大保护窗口，例如 370 天，防止错误配置导致死循环。

#### 任务 C4：实现 `recent_trading_days()`

**任务内容:**

- 输入 market、end_date、count。
- 返回截至 end_date 的最近 count 个交易日。
- 返回顺序为升序，便于 backfill 按时间写入。

**成功标准:**

- [ ] `count=5` 返回 5 个交易日，不包含周末。
- [ ] 返回日期升序排列。
- [ ] end_date 为非交易日时，从前一个交易日开始回溯。
- [ ] count 小于等于 0 时 fail fast 或返回空列表，行为有测试固定。

#### 任务 C5：实现 `should_run_daily_job()`

**任务内容:**

- 输入 market 和 now。
- 根据 now 对应的交易日期判断是否应执行日频任务。
- 第一版只判断是否交易日，不做盘中时间窗口判断。

**成功标准:**

- [ ] 交易日返回 `(True, None)`。
- [ ] 非交易日返回 `(False, reason)`。
- [ ] reason 可直接写入 run error_message 或 params。

---

### 模块 D：`src/market_calendar/__init__.py`

职责：提供默认服务实例。

建议接口：

```python
_calendar_service: TradingCalendarService | None = None


def get_trading_calendar() -> TradingCalendarService:
    ...
```

#### 任务 D1：新增默认获取函数

**任务内容:**

- 新增 `get_trading_calendar()`。
- 返回单例 `TradingCalendarService`。
- 支持测试 monkeypatch。

**成功标准:**

- [ ] scheduler 可通过 `get_trading_calendar()` 获取服务。
- [ ] backfill 可通过 `get_trading_calendar()` 获取服务。
- [ ] 单测可 monkeypatch 替换为 fake calendar。

---

### 模块 E：`src/scheduler/daily_scheduler.py`

职责：在日频任务中接入交易日历，休市日主动 skipped。

#### 任务 E1：在 `_run_daily_job()` 中加入交易日判断

**任务内容:**

当前流程：

```text
抢锁 → 查重复 run → 创建 auto run → 执行交易逻辑
```

目标流程：

```text
抢锁 → 查重复 run → 获取账户 → 判断交易日 → 非交易日创建 skipped run → 交易日创建 running run → 执行交易逻辑
```

建议伪代码：

```python
session = calendar.get_session(market, today)
account = store.get_or_create_account(market, "auto")

if not session.is_trading_day:
    run = store.create_run(..., params={"calendar_reason": session.reason})
    store.update_run_status(run.run_id, "skipped", session.reason)
    store.finish_job_lock(job_key, "skipped", session.reason)
    return
```

**成功标准:**

- [ ] 非交易日不会进入 `_execute_daily_trading()`。
- [ ] 非交易日会创建一条 `auto` run。
- [ ] run.status 为 `skipped`。
- [ ] run.error_message 或 params 中包含休市原因。
- [ ] job lock 状态为 `skipped`。
- [ ] 交易日仍按原路径创建 running run 并进入执行逻辑。

#### 任务 E2：调整重复运行判断包含 skipped

**任务内容:**

- `check_run_exists()` 的自动调度阻断状态建议包含：

```text
running
success
skipped
```

**成功标准:**

- [ ] 同一天已有 skipped auto run 时，重复触发不会再次创建 skipped run。
- [ ] 同一天 failed auto run 是否允许重跑由测试固定，默认建议允许重跑。

#### 任务 E3：保留 cron，不做动态 job 注册

**任务内容:**

- 保持 A 股和美股 cron 不变。
- 不引入按交易日动态注册 APScheduler job。

**成功标准:**

- [ ] `a_share_daily` job 仍存在。
- [ ] `us_daily` job 仍存在。
- [ ] job 的 timezone/max_instances/coalesce/misfire_grace_time 不退化。

---

### 模块 F：`src/paper_ledger/backfill.py`

职责：让 backfill 按交易日补净值，而不是自然日。

#### 任务 F1：`backfill_recent_days()` 接收 calendar 参数

**任务内容:**

修改签名：

```python
def backfill_recent_days(
    store: PaperLedgerStore,
    market: str,
    days: int = 30,
    daily_return: float = 0.001,
    calendar: TradingCalendarService | None = None,
) -> int:
```

**成功标准:**

- [ ] 不传 calendar 时使用默认 `get_trading_calendar()`。
- [ ] 测试可传 fake calendar。
- [ ] 原有调用方无需大改。

#### 任务 F2：按 `recent_trading_days()` 生成待补日期

**任务内容:**

替换当前自然日逻辑：

```python
for i in range(days, 0, -1):
    trade_date = today - timedelta(days=i)
```

改为：

```python
trade_dates = calendar.recent_trading_days(market, today, days)
for trade_date in trade_dates:
    ...
```

**成功标准:**

- [ ] backfill 不生成周末 nav。
- [ ] backfill 不生成静态节假日 nav。
- [ ] `days=30` 表示最近 30 个交易日。
- [ ] 返回 completed 仍表示本次实际新增成功的交易日数量。

#### 任务 F3：backfill run 的 params 记录日历语义

**任务内容:**

在 run params 中记录：

```json
{
  "backfill_days": 30,
  "calendar_mode": "trading_days",
  "daily_return": 0.001
}
```

**成功标准:**

- [ ] run params 能看出本次 backfill 是按交易日生成。
- [ ] Dashboard/history 排查时可以区分旧自然日 backfill 和新交易日 backfill。

---

### 模块 G：`src/paper_ledger/store.py`

职责：支持 skipped 状态阻断和状态展示。

#### 任务 G1：默认 blocking_statuses 增加 skipped

**任务内容:**

当前默认建议改为：

```python
blocking_statuses=("running", "success", "skipped")
```

**成功标准:**

- [ ] 已有 skipped run 时，`check_run_exists()` 返回 True。
- [ ] failed run 不阻断重试。
- [ ] 单测覆盖 running/success/skipped/failed。

#### 任务 G2：状态注释补充 skipped

**任务内容:**

- ORM 字段 comment 中补充 `skipped`。
- docs 中补充状态语义。

**成功标准:**

- [ ] `PaperRunRow.status` 注释包含 skipped。
- [ ] `ScheduledJobLockRow.status` 注释包含 skipped。
- [ ] 文档状态语义统一。

---

### 模块 H：`src/api/routes_dashboard.py`

职责：Dashboard 展示交易日历影响后的自动化状态。

#### 任务 H1：扩展 automation payload

**任务内容:**

当前 payload：

```json
{
  "today_status": "pending",
  "last_run_at": null,
  "next_run_at": null
}
```

建议扩展：

```json
{
  "today_status": "skipped",
  "last_run_at": "2026-06-19T09:15:00+08:00",
  "next_cron_at": "2026-06-22T09:15:00+08:00",
  "next_trading_run_at": "2026-06-22T09:15:00+08:00",
  "calendar_reason": "A股今日休市",
  "next_trading_day": "2026-06-22"
}
```

**成功标准:**

- [ ] 仍兼容当前 Dashboard 渲染所需字段。
- [ ] skipped 状态时能展示 calendar_reason。
- [ ] next_cron_at 与 next_trading_run_at 概念明确。
- [ ] 单测覆盖无运行记录、success、failed、skipped。

#### 任务 H2：从 latest auto run 提取 skipped reason

**任务内容:**

- latest auto run 若 status 为 skipped，则读取 error_message。
- 将 error_message 映射为 `calendar_reason`。

**成功标准:**

- [ ] 休市日自动任务卡片显示“今日跳过”。
- [ ] 显示具体休市原因。
- [ ] 不把 skipped 误展示为 failed。

#### 任务 H3：计算 next_trading_run_at

**任务内容:**

- 使用 `TradingCalendarService.next_trading_day()`。
- A 股使用 09:15 北京时间。
- 美股第一版使用当前既有 21:15 北京时间。

**成功标准:**

- [ ] 周五后 next_trading_run_at 跳过周末到下周一。
- [ ] 节假日前后跳过休市日期。
- [ ] 与 next_cron_at 区分展示。

---

### 模块 I：测试

职责：锁定交易日历行为，避免后续回归。

#### 任务 I1：新增 `tests/test_market_calendar.py`

**测试内容:**

- 普通工作日是交易日。
- 周末不是交易日。
- A 股静态节假日不是交易日。
- 美股静态节假日不是交易日。
- next_trading_day 跳过周末。
- recent_trading_days 返回升序日期。

**成功标准:**

- [ ] 覆盖 `get_session()`。
- [ ] 覆盖 `is_trading_day()`。
- [ ] 覆盖 `previous_trading_day()`。
- [ ] 覆盖 `next_trading_day()`。
- [ ] 覆盖 `recent_trading_days()`。

#### 任务 I2：更新 `tests/test_daily_scheduler.py`

**测试内容:**

- 非交易日 `_run_daily_job()` 创建 skipped run。
- 非交易日不调用 `_execute_daily_trading()`。
- 交易日仍进入执行路径。
- 同日 skipped run 阻断重复创建。

**成功标准:**

- [ ] scheduler 休市日行为被测试固定。
- [ ] job lock skipped 行为被测试固定。
- [ ] 未实现交易逻辑仍不会误标 success。

#### 任务 I3：更新 `tests/test_paper_ledger_backfill.py`

**测试内容:**

- fake calendar 返回指定交易日列表。
- backfill 只写这些交易日。
- 周末/节假日不产生 nav。
- 第二次 backfill 幂等返回 0。

**成功标准:**

- [ ] `days` 语义从自然日切换为交易日后有测试保障。
- [ ] backfill 仍保持幂等。

#### 任务 I4：更新 Dashboard 相关测试

**测试内容:**

- automation payload 包含 calendar_reason。
- skipped 不展示为 failed。
- next_trading_run_at 跳过非交易日。

**成功标准:**

- [ ] Dashboard API contract 测试通过。
- [ ] 页面契约测试通过。
- [ ] 前端没有依赖已删除字段。

---

### 模块 J：文档与运维说明

职责：说明交易日历语义和维护方式。

#### 任务 J1：更新 scheduler issue 文档

**任务内容:**

- 在 `docs/2026-06-19-scheduler-architecture-issues.md` 中补充交易日历接入状态。
- 标记哪些问题被本计划覆盖。

**成功标准:**

- [ ] issue 文档能追踪交易日历整改进度。
- [ ] P2 “未接入交易日历”有明确落地链接。

#### 任务 J2：新增 runbook 小节

**任务内容:**

在 runbook 中说明：

- 如何维护静态节假日表。
- skipped 状态是什么意思。
- next_cron_at 和 next_trading_run_at 的区别。
- 如果发现休市日误判，如何修正。

**成功标准:**

- [ ] 运维人员能看懂 skipped 不是失败。
- [ ] 能按文档补充节假日。
- [ ] 能解释 Dashboard 自动任务状态。

---

## 5. 推荐实施顺序

### Phase 1：最小交易日历服务

范围：模块 A、B、C、D、I1。

目标：先把统一交易日历服务做出来。

成功标准：

- [ ] `TradingCalendarService` 可用。
- [ ] 周末/静态节假日判断正确。
- [ ] `tests/test_market_calendar.py` 通过。

---

### Phase 2：接入 scheduler

范围：模块 E、G、I2。

目标：休市日 auto run 进入 skipped，不进入交易逻辑。

成功标准：

- [ ] 休市日不调用 `_execute_daily_trading()`。
- [ ] 创建 skipped run。
- [ ] job lock 标记 skipped。
- [ ] 重复触发不会重复创建 skipped run。

---

### Phase 3：接入 backfill

范围：模块 F、I3。

目标：backfill 从自然日切换为交易日。

成功标准：

- [ ] 最近 30 天改为最近 30 个交易日。
- [ ] 周末/休市日不生成 nav。
- [ ] 第二次 backfill 幂等。

---

### Phase 4：接入 Dashboard

范围：模块 H、I4。

目标：Dashboard 正确展示 skipped 和下一真实交易日运行时间。

成功标准：

- [ ] automation payload 包含 calendar_reason。
- [ ] next_cron_at 与 next_trading_run_at 分离。
- [ ] Dashboard 测试通过。

---

### Phase 5：文档收尾

范围：模块 J。

目标：把交易日历维护方式和状态语义沉淀下来。

成功标准：

- [ ] issue 文档更新。
- [ ] runbook 更新。
- [ ] 计划文档状态可用于后续实现跟踪。

---

## 6. 不在第一版做的事情

第一版明确不做：

- 不接数据库表 `market_sessions`。
- 不做外部交易所日历同步。
- 不做美股提前收盘精确处理。
- 不动态注册 APScheduler job。
- 不做实盘订单时间窗 gate。
- 不引入复杂 provider 链。

这些放到后续版本，避免第一版过重。

---

## 7. 后续增强路线

### V2：日历落库

新增表：

```text
market_sessions
market_calendar_sync_runs
```

能力：

- 缓存某一年交易日历。
- 支持人工修正。
- Dashboard 可查看日历来源和更新时间。

### V3：外部数据源同步

能力：

- A 股从 AkShare / 交易所日历同步。
- 美股从可靠交易日历源同步。
- 同步失败时 fail closed，不默认当交易日。

### V4：实盘执行前置 gate

能力：

- 非交易日禁止生成实盘订单。
- 非交易时间禁止提交订单。
- 提前收盘日调整执行窗口。
- calendar gate 与 kill switch 一起作为实盘安全闸。

---

## 8. 总体验收标准

完成第一版交易日历接入后，应满足：

- [ ] A 股周末不会执行 auto 交易逻辑。
- [ ] A 股静态休市日不会执行 auto 交易逻辑。
- [ ] 美股周末不会执行 auto 交易逻辑。
- [ ] 美股静态休市日不会执行 auto 交易逻辑。
- [ ] 非交易日会生成 skipped run，且有 reason。
- [ ] skipped run 会阻止同日重复 skipped。
- [ ] backfill 只生成交易日 nav。
- [ ] Dashboard 能展示 skipped reason。
- [ ] Dashboard 能区分 next_cron_at 和 next_trading_run_at。
- [ ] 所有新增和受影响测试通过。

---

## 9. 建议检查命令

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_market_calendar.py -q
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_daily_scheduler.py -q
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_paper_ledger_backfill.py -q
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_api.py tests/test_dashboard_performance.py tests/test_dashboard_page_contract.py -q
```

---

## 10. 最小落地定义

最小可接受落地不是“有一个日历类”，而是：

```text
scheduler 休市日 skipped
backfill 只补交易日
Dashboard 能解释 skipped
测试固定以上行为
```

只有这四件事同时完成，交易日历接入才算真正闭环。
