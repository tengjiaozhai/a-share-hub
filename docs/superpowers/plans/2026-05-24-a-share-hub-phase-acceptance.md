# A-Share Hub 分阶段验收标准

## 使用规则

- 所有阶段采用硬门禁：前一阶段未通过，禁止进入下一阶段。
- 每个阶段都必须同时满足“自动化测试通过”“手工验证证据齐全”“文档已更新”三个条件。
- 所有命令都在仓库根目录 `/Users/shenmingjie/workSpace/tranding/a-share-hub` 执行。

## Phase 1：文档基线纠偏

**目标：** 让 `docs/missing-features-analysis.md` 成为可信的现状描述，而不是乐观估算。

**必须交付：**

- `docs/missing-features-analysis.md` 增加“实现深度分级”。
- 文档明确补入 `execution_order`、`kill_switch_event`、`decide`。
- 文档将 `pull_execution_plans.py` 从“stub”改成“缺失”。

**自动化验收：**

运行：`pytest tests/test_docs_alignment.py -v`
预期：PASS

**手工验收：**

- `rg -n "实现深度分级|execution_order|kill_switch_event|`decide`|pull_execution_plans.py" docs/missing-features-analysis.md`
- 审核文档时必须能回答三件事：当前哪些能力只是存在文件、哪些能力已接线、哪些能力已验收。

**阻塞条件：**

- 文档仍使用单一百分比表达进度。
- 文档仍把 `run-decision`/`plan-execution` 当成最终命令边界。

## Phase 2：决策持久化与目标仓位闭环

**目标：** 让决策不再是瞬时字符串，而是可回放、可查询、可导出目标仓位的结构化资产。

**必须交付：**

- Alembic 迁移新增 `decision_runs`、`decision_input_snapshots`、`target_positions`。
- `RuntimeStore` 支持 `insert_decision_run`、`get_decision_run`、`list_decision_runs`、`insert_target_position`、`list_active_target_positions`。
- `src/decision/decision_runner.py` 与 `src/portfolio/target_planner.py` 输出可持久化字段。

**自动化验收：**

运行：`pytest tests/test_decision_runtime_store.py tests/test_decision_runner.py tests/test_target_planner.py -v`
预期：PASS

运行：`/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head`
预期：PASS，无迁移错误。

**手工验收：**

- 运行：`/opt/anaconda3/envs/py311/bin/python3 -m src.main decide --symbols 600519.SH --mock-llm`
- 检查数据库里存在一条 `decision_run`、一条 `decision_input_snapshot`、一条 `target_position`。
- 同一个 `decision_run_id` 可以追溯到输入快照和目标仓位。

**阻塞条件：**

- 决策结果只打印到 stdout，没有写入数据库。
- `target_position` 无法关联到 `decision_run_id`。

## Phase 3：执行订单、API/CLI 边界与对账状态

**目标：** 把主流程收敛到 `decide -> portfolio-targets -> execution-plans -> broker-events -> reconciliation`。

**必须交付：**

- 数据侧新增 `execution_order`、`risk_gate_event`、`kill_switch_event`。
- API 暴露 `/api/v1/decision-runs`、`/api/v1/decision-runs/{id}`、`/api/v1/portfolio-targets/active`、`/api/v1/reconciliation/status`。
- CLI 收敛为 `decide`、`shadow-execute`、`live-execute`、`reconcile`、`halt`。
- `routes_dashboard.py` 不再返回硬编码示例数据。

**自动化验收：**

运行：`pytest tests/test_cli.py tests/test_bootstrap.py tests/test_decision_runtime_store.py tests/test_execution_plan_api.py tests/test_runtime_store_pg.py tests/test_reconciliation.py tests/test_oms_state_machine.py tests/test_kill_switch_pg.py -v`
预期：PASS

**手工验收：**

- `curl http://127.0.0.1:8000/api/v1/decision-runs`
- `curl http://127.0.0.1:8000/api/v1/portfolio-targets/active`
- `curl http://127.0.0.1:8000/api/v1/reconciliation/status`
- `curl http://127.0.0.1:8000/api/v1/dashboard/status`

以上四个接口必须返回来自运行时存储的真实数据，而不是静态样例。

**阻塞条件：**

- `decide` 仍然只打印 stdout，没有写入 `decision_runs` 或 `target_positions`。
- `halt` 仍然只打印 stdout，没有写入 `kill_switch_event`。
- `run-decision` 或 `plan-execution` 仍然存在于 CLI 对外接口中。
- `dashboard/status` 仍写死 `total_decisions=0`、`total_orders=0` 之类示例值。

## Phase 4：Windows 轮询执行器与 fail-closed 风控

**目标：** 补齐 Windows 单一执行器，使 shadow 模式具备真实的“拉计划 -> 本地风控 -> 回传事件 -> ack -> 对账”链路。

**必须交付：**

- `windows_agent/pull_execution_plans.py` 存在并可 `--once` 执行。
- 本地风控至少覆盖：终端断连、可用资金不足、可卖数量不足。
- 云端风控至少覆盖：`kill_switch`、过期决策、重复下单。
- `halt` 可以记录 `kill_switch_event`，并阻断新的执行计划。

**自动化验收：**

运行：`pytest tests/test_windows_gateway_logic.py tests/test_risk_gate.py tests/test_e2e_shadow_cycle.py -v`
预期：PASS

**手工验收：**

- 启动 API：`/opt/anaconda3/envs/py311/bin/python3 -m src.main serve`
- 单次轮询：`/opt/anaconda3/envs/py311/bin/python3 windows_agent/pull_execution_plans.py --once --base-url http://127.0.0.1:8000`
- 触发停机：`/opt/anaconda3/envs/py311/bin/python3 -m src.main halt --reason "manual gate"`
- 再次轮询时，必须无新单提交。

**阻塞条件：**

- `pull_execution_plans.py` 不存在，或只包含空函数。
- 风控失败时仍会继续 ack 计划或提交订单。

## Phase 5：进入实盘前的硬门禁

**目标：** 明确“shadow-ready”不等于“live-ready”，在进入实盘前保留必须补齐的门槛。

**必须交付：**

- `docs/evalution.md` 中要求的 1m/5m 行情、交易日历、午间休市、集合竞价、停牌、板块规则差异被纳入实现计划。
- 合规侧至少具备：策略版本记录、程序化交易报备材料清单、测试记录、应急停机流程、审计日志方案。
- 至少连续 `10` 个交易日 shadow 运行，决策输出与执行计划链路无人工修库。

**自动化验收：**

运行：`pytest tests/test_market_rules.py tests/test_market_clock.py tests/test_load_gate_policy.py -v`
预期：PASS

**手工验收：**

- 抽查 `10` 个交易日 shadow 日志，确认每个 `decision_run` 都能关联到 `target_position`、`execution_order`、`broker_event`、`reconciliation status`。
- 检查实盘前清单是否已获得人工签字：运维、策略负责人、执行终端负责人。

**阻塞条件：**

- 没有连续 shadow 运行证据。
- 仍缺失 1m/5m 行情或 A 股关键交易规则。
- 合规资料只存在口头描述，没有落到仓库文档或结构化记录。

## 阶段切换原则

- Phase 1 通过后，才允许开始任何实体和迁移开发。
- Phase 2 通过后，才允许暴露新 API 和新 CLI。
- Phase 3 通过后，才允许编写 Windows 轮询执行器。
- Phase 4 通过后，才允许讨论灰度实盘。
- Phase 5 全部通过前，默认系统只能标记为 `shadow-ready`，不得标记为 `live-ready`。
