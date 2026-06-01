# Alpha Tokenized Securities Half-Automated Desk Design

> 生成日期：2026-06-01
> 状态：已基于当前仓库现状完成差距评估，并收敛为 Phase 1 计划

---

## 1. 目标

将当前仓库里的 `crypto + dashboard` 从“加密货币监控壳 + A 股 shadow 工作台”改造成 `币安 alpha 代币化证券半自动执行台`。

这里的“半自动执行台”含义固定为：

- 系统负责行情、对象模型、研究上下文、标准化建议单、风控结论、操作台展示、执行回填、基础对账和审计留痕。
- 系统不假设存在可用的 alpha 代币化证券自动下单接口。
- 人工执行不是临时补丁，而是正式链路的一部分。
- 执行回填后的结果才是仓位、PnL 和复盘的权威来源。

---

## 2. 当前状态结论

当前仓库距离目标仍然较远，整体成熟度约为 `25%`，大致位于“演示/骨架”和“研究监控台”之间，还没有进入真正的半自动执行台阶段。

现有基础：

- `src/api/dashboard.html` 已经有 crypto 视图，但本质仍是监控面板，不是人工执行工单台。
- `src/api/routes_crypto.py` 已暴露状态、余额、持仓、订单、信号、指标端点，但大部分返回的是临时 mock 数据。
- `src/storage/runtime_store.py` 和 `src/storage/models.py` 已经具备 `execution_plans`、`execution_orders`、`broker_events` 等运行时底座。
- `src/crypto/` 下已有指标、订单管理、风险管理、Binance spot/testnet 风格客户端骨架。

主要断点：

- 没有 alpha 代币化证券的真实对象模型。
- 没有“建议单 -> 人工确认 -> 执行回填 -> 对账”权威链路。
- 没有以人工执行为中心的账本和审计语义。
- dashboard 仍然不是操作台。

---

## 3. 外部约束

本设计基于以下约束：

- 当前公开可确认的 Binance alpha tokenized securities 材料，重点落在资产信息、市场状态、K 线、限额等公开信息。
- 当前未发现可直接作为正式生产前提的公开自动下单接口文档。
- 因此本项目不以“自动下单闭环”为目标，而以“半自动执行闭环”为目标。

这不是对 Binance 内部能力的绝对判断，而是对当前公开资料的保守建模。后续如果出现明确的公开交易接口文档，可以在后续计划中扩展执行层，但不影响本轮设计。

---

## 4. 目标架构

目标系统保留单一权威路径：

1. `Alpha 市场数据层`
   - 读取 alpha 代币化证券公开资料
   - 归一化资产主数据、市场状态、限额和动态快照

2. `建议单与风控层`
   - 基于研究输入和市场上下文生成标准化建议单
   - 给出明确的风险结论和失效时间

3. `人工执行层`
   - 操作员确认、驳回或执行建议单
   - 回填实际执行结果
   - 记录执行来源、时间、价格、数量、备注和证据

4. `账本与对账层`
   - 以人工回填结果更新仓位、成本和基础 PnL
   - 记录异常和状态漂移

5. `操作台`
   - 同时展示资产状态、建议单、执行状态、持仓、PnL、异常和审计线索

---

## 5. 设计原则

- 一个行为只保留一个权威实现路径。
- 先把对象模型和人工执行闭环打通，再讨论更复杂的信号自动化。
- phase 1 不做自动下单兼容层，不做双轨执行桥接。
- 对暂停交易、市场关闭、限额异常、失效建议单，默认 fail fast。
- 现有 A 股 shadow 工作台保留，但 alpha 目标链路不复用 A 股语义做“软兼容”。

---

## 6. 子项目拆分

这个目标覆盖多个独立子系统，不适合写成一份失控的大计划。拆成 4 个顺序子项目：

### 子项目 A：Alpha 数据基础与标准化

目标：

- 建立 alpha 资产主数据模型
- 接入公开市场状态和动态快照
- 提供统一内部 schema

产出：

- alpha 公共客户端
- 归一化 service
- alpha 只读 API

### 子项目 B：建议单与人工执行纵切面

目标：

- 建立标准化建议单实体
- 建立人工确认、驳回、执行回填的状态机
- 将结果写入权威运行时存储

产出：

- ticket API
- fill-back API
- dashboard 操作台最小闭环

### 子项目 C：账本、PnL、对账和异常处理

目标：

- 用回填事件更新持仓、成本、现金和基础 PnL
- 提供漂移检测与异常视图

产出：

- alpha position ledger
- reconciliation status
- ops 异常清单

### 子项目 D：研究自动化与操作台增强

目标：

- 将研究输入、信号规则、观察列表、优先级排序接入建议单生成
- 打磨 dashboard 的实际操作体验

产出：

- 建议单自动生成器
- 更完整的监控与审计视图

---

## 7. Phase 1 选择

本轮计划只覆盖第一个真正可执行的纵切面：

`Alpha 数据基础 + 建议单与人工执行最小闭环`

Phase 1 的成功标准：

- 可以从 alpha 公开资料读取并归一化资产与市场状态。
- 可以创建、查看、确认和驳回建议单。
- 可以回填人工执行结果，并将结果持久化为权威事件。
- dashboard 出现可操作的 alpha 面板，而不是静态 crypto 监控块。
- 所有新增行为都有测试覆盖。

Phase 1 明确不做：

- 自动下单
- 完整的 realized/unrealized PnL 账本
- 完整公司行为处理
- 全量研究自动化
- A 股与 alpha 的统一净敞口视图

---

## 8. 文件边界

为避免把错误语义塞进现有 `src/crypto/`，phase 1 为 alpha 建立独立边界：

- `src/alpha/`
  - alpha 资产模型、客户端和 service
- `src/api/routes_alpha.py`
  - alpha 只读数据与人工执行 API
- `src/storage/models.py`
  - 为 alpha 建议单和人工执行回填增加专用表
- `src/storage/runtime_store.py`
  - 为 alpha ticket/fill/summary 提供权威写入与读取接口
- `src/api/routes_dashboard.py`
  - 将 alpha 数据并入 workbench payload
- `src/api/dashboard.html`
  - 将当前 crypto 监控区改造成 alpha 操作区

---

## 9. 测试策略

phase 1 采用 TDD，至少覆盖：

- alpha 公共客户端的响应归一化
- alpha 资产和市场状态 API
- 建议单状态机
- 人工执行回填 API
- dashboard alpha 区域的静态结构
- dashboard workbench payload 的 alpha 合同

测试不依赖真实 Binance 网络响应，统一通过 fixture 或 monkeypatch 固定外部数据。

---

## 10. 风险

主要风险：

- 公开 alpha 数据结构可能变化
- 当前 runtime store 语义偏 A 股 shadow，扩展时容易混入错误语义
- dashboard 已较大，继续往一个 HTML 文件堆逻辑容易失控

对应策略：

- 先做 `raw -> normalized` 的隔离 client/service
- alpha ticket/fill 使用独立表和独立 store 方法，不复用错语义字段
- 本轮只扩展 alpha 必要 UI，不顺手重做整个 dashboard

---

## 11. 下一步

下一步不再继续做全局抽象讨论，而是进入 `Phase 1: Alpha 数据基础 + 人工执行纵切面` 的详细实施计划。
