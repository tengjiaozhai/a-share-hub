# A 股全自动实盘可行性评估与收敛方案

## Summary
- 基于 [PLAN_a_stock_trading_hub.md](/Users/shenmingjie/workSpace/tranding/PLAN_a_stock_trading_hub.md:16) 和 [deep-research-report (1).md](</Users/shenmingjie/workSpace/tranding/deep-research-report (1).md:5>)，当前方案可以较高把握落地成“云端研究/信号/风控 + Windows 执行网关 + 模拟盘”，但**不能直接落地成你要求的“LLM 主决策、盘中低频、全自动 A 股实盘”**。
- 关键原因不是 QMT 接不上，而是当前设计把“研究意图”和“执行状态机”压成了一个 `trade_intent`，且模拟成交仍是“按 latest close 成交”，Windows 侧也只是 stub；这对实盘 OMS 不够，[现有流程定义见]( /Users/shenmingjie/workSpace/tranding/PLAN_a_stock_trading_hub.md:521 )、[分阶段计划见]( /Users/shenmingjie/workSpace/tranding/PLAN_a_stock_trading_hub.md:932 )。
- “不阉割逻辑”可以成立，但前提是：**完整多智能体推理只发生在离散决策层，不发生在订单执行层**。执行层必须是确定性的 OMS/风控状态机。这不是削弱逻辑，而是把推理和执行放到正确层级。
- 可行性结论：**有条件可行**。条件是把当前计划重构为“决策引擎 + OMS + QMT 执行网关”的单路径实盘架构；如果你坚持“全市场、每个周期、全量多 agent 深推理”，在计划里写明的 `2核/2GB` 资源约束下不可行。

## Public Interfaces / Architecture Changes
- 替换当前权威主流程。新主流程应为：`market snapshot -> candidate filter -> LLM decision run -> portfolio target -> deterministic risk gate -> execution plan -> broker orders -> broker events -> reconciliation`。`paper broker` 只保留为 shadow 模式，不再是主抽象。
- 替换当前 `trade_intent` 单对象设计。新增或就地替换为这些权威实体：`decision_run`、`decision_input_snapshot`、`target_position`、`execution_order`、`broker_order_event`、`account_snapshot`、`position_snapshot`、`risk_gate_event`、`kill_switch_event`。`analysis_signal` 只保留为研究产物，不再直接驱动执行。
- 修改云端 API。把 `/trade-intents/pending` 改为以“目标仓位/执行计划”为核心，例如 `/portfolio-targets/active`、`/execution-plans/ready`、`/broker-events`、`/reconciliation/status`、`/kill-switch`、`/decision-runs/{id}`。
- 修改 CLI/任务边界。把 `analyze` / `paper-trade` 拆成 `decide`、`shadow-execute`、`live-execute`、`reconcile`、`halt`。Windows 节点成为唯一实盘执行者，云端不直接持有下单能力。
- 修改数据粒度。当前计划基于 `120` 个交易日 K 线和 mock news，不足以支撑盘中低频实盘；需要统一到 `1m/5m` 级别行情、交易日历、午间休市、集合竞价、停牌、复权、涨跌停、板块规则、T+1 卖出限制。
- 修改 LLM 输出语义。LLM 不能再输出“准订单”，而要输出“目标仓位/仓位变化/失效时间/风险理由”。订单拆分、价格选择、撤改、重试、去重、部分成交处理都必须由确定性执行层完成。
- 默认把全量推理限制在候选集上。推荐先用确定性预筛覆盖全市场，再对每个周期的前 `10-20` 只候选股运行完整多 agent 推理。若拒绝预筛并要求全市场逐周期深推理，则直接判定当前资源预算下不可落地。

## Required Implementation Changes
- 决策层：固定在离散时间点运行，默认 `15` 分钟一轮，仅在 `09:35-11:25`、`13:05-14:55` 触发；持久化完整输入快照、模型版本、Prompt 哈希、原始输出、结构化结果和最终目标仓位，保证可回放。
- OMS 层：实现幂等下单、部分成交、撤单/改价、订单超时、断线重连、重复回报去重、持仓与资金对账、单执行器租约、心跳失联保护。Windows QMT 节点必须在 broker 视角上保持单一权威状态。
- 风控层：在当前规则基础上补齐账户现金校验、可卖数量校验、重复下单抑制、过期决策拒绝、单周期最大换手、单票单日累计成交额、异常收益/回撤熔断、数据延迟熔断、执行漂移熔断。
- 合规层：把程序化交易报备、策略版本管理、测试记录、应急预案、快速停机、撤单总开关、日志留痕作为一等功能，而不是文档说明。按现行监管口径，程序化交易是“先报告、后交易”，且系统要具备阈值管理、异常监测、错误处理和人工干预能力。
- 部署层：Linux `2GB` 节点只负责调度、特征计算、LLM 调用和只读 API，不负责实盘执行；Windows QMT 节点本地保存最小必要状态并持续对账，一旦 broker 状态与云端状态漂移或长时间断连，自动停机。

## Test Plan
- 决策回放测试：同一市场快照、同一模型配置、同一 prompt 模板下，系统必须稳定产出可解析的结构化结果，并能完整回放当时的输入与最终目标。
- 市场规则测试：覆盖 A 股 T+1、涨跌停、ST/风险警示、午间休市、集合竞价、停牌、退市整理、不同板块涨跌幅差异。
- OMS 测试：覆盖部分成交、拒单、撤单失败、断线重连、重复回报、延迟回报、云端与本地状态不一致。
- 风控测试：覆盖 LLM 超时、JSON 解析失败、数据陈旧、账户资金不足、可卖不足、KILL_SWITCH 开启、当日换手超限、连续亏损熔断。
- Shadow 验证：先做 `2-4` 周只读 + shadow 交易，要求“同一决策输出在 shadow/live pre-submit 路径上的订单计划一致”，再进入极小资金实盘灰度。

## Assumptions And Sources
- 本评估基于当前仓库只有两份方案文档、尚无实现代码这一事实。
- 目标已锁定为：`全自动实盘`、`盘中低频`、`LLM 主决策者`、`已有 QMT/MiniQMT 权限`。
- 当前监管和交易约束必须内建到系统里，而不能靠人工记忆。参考：
  - [中国证监会《证券市场程序化交易管理规定（试行）》](https://www.csrc.gov.cn/ningxia/c104435/c7556824/7556824/files/%E9%99%84%E4%BB%B61%EF%BC%9A%E8%AF%81%E5%88%B8%E5%B8%82%E5%9C%BA%E7%A8%8B%E5%BA%8F%E5%8C%96%E4%BA%A4%E6%98%93%E7%AE%A1%E7%90%86%E8%A7%84%E5%AE%9A%EF%BC%88%E8%AF%95%E8%A1%8C%EF%BC%89.pdf)
  - [上交所程序化交易管理实施细则，2025-07-07 生效](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20250612_10781696.shtml)
  - [深交所程序化交易管理实施细则，2025-07-07 生效](https://docs.static.szse.cn/www/lawrules/rule/trade/W020250403603802169453.pdf)
  - [XtQuant FAQ：需先启动 MiniQMT，XtTrader 负责报单/撤单/查询/推送](https://docs.thinktrader.net/pages/040ff7/)
  - [上交所交易时间说明](https://one.sse.com.cn/onething/gptz/)
  - [上交所 2026-04-24 发布《交易规则》修订，2026-07-06 生效](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20260424_10816474.shtml)
- 最终硬结论：如果“完整逻辑”指“LLM 在每个决策周期进行完整推理，执行层确定性落单”，则可以做；如果“完整逻辑”指“LLM 在线控制每笔订单、每次撤改单、每次 broker 回报处理”，则不建议，也不应作为可生产上线方案。
