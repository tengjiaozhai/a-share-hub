from alembic import op


revision = "20260606_000008"
down_revision = "20260603_000007"
branch_labels = None
depends_on = None


TABLE_COMMENTS = {
    "a_share_watchlist": "A股自选股列表，用于工作台和A股扫描页面保存用户关注的股票。",
    "account_snapshots": "模拟账户快照表，记录每次模拟执行后的现金、净值和持仓。",
    "alembic_version": "Alembic数据库迁移版本表，用于记录当前数据库结构版本。",
    "alpha_api_order_attempts": "Alpha接口下单尝试记录表，保存每次对外部执行接口的请求和响应。",
    "alpha_manual_fills": "Alpha人工成交记录表，保存人工录入的成交数量、价格和备注。",
    "alpha_portfolio_snapshots": "Alpha组合快照表，记录现金、已实现盈亏、未实现盈亏和净值。",
    "alpha_positions": "Alpha持仓表，记录每个标的当前数量、成本和盯市价格。",
    "alpha_reconciliation_runs": "Alpha对账运行记录表，保存每次对账来源、状态和差异明细。",
    "alpha_tickets": "Alpha交易工单表，保存研究候选转成的待审批或已执行交易意图。",
    "alpha_watchlist_items": "Alpha研究观察列表，保存用于研究扫描的标的及优先级。",
    "broker_events": "券商或模拟券商事件流水表，记录订单提交、成交和对账事件。",
    "decision_input_snapshots": "决策输入快照表，保存每次LLM或策略决策使用的上下文。",
    "decision_runs": "决策运行表，记录每次策略或LLM对单个标的给出的BUY、SELL、HOLD建议。",
    "execution_orders": "执行订单表，保存由目标仓位转成的模拟或真实执行订单。",
    "execution_plans": "执行计划表，保存可被执行节点消费的计划指令。",
    "kill_switch_events": "停机开关事件表，保存每次启用或解除停机的审计记录。",
    "kill_switch_state": "停机开关当前状态表，全局控制是否允许继续产生交易动作。",
    "risk_gate_events": "交易前风控事件表，记录每次风控放行或拦截的原因。",
    "target_positions": "目标仓位表，保存决策后希望达到的仓位金额和比例。",
    "us_watchlist": "美股自选股列表，用于工作台和美股页面保存用户关注的股票。",
    "user_preferences": "用户偏好表，保存工作台配置、观察列表和展示偏好。",
}


COLUMN_COMMENTS = {
    "a_share_watchlist": {
        "id": "自选股记录的自增主键。",
        "symbol": "A股代码，使用系统内部格式，例如600519.SH。",
        "name": "股票名称，例如贵州茅台。",
        "sort_order": "列表排序值，数值越小展示越靠前。",
        "created_at": "记录创建时间。",
    },
    "account_snapshots": {
        "snapshot_id": "账户快照唯一ID。",
        "cash": "快照时账户可用现金。",
        "nav": "快照时账户净值，等于现金加持仓市值。",
        "positions_json": "持仓明细JSON，记录每个标的的数量和成本。",
        "created_at": "快照创建时间。",
    },
    "alembic_version": {
        "version_num": "当前已执行到的Alembic迁移版本号。",
    },
    "alpha_api_order_attempts": {
        "attempt_id": "接口下单尝试唯一ID。",
        "ticket_id": "关联的Alpha交易工单ID。",
        "asset_symbol": "实际下单标的代码。",
        "action": "下单方向，例如BUY或SELL。",
        "quantity": "本次尝试下单数量。",
        "limit_price": "本次尝试使用的限价。",
        "mode": "执行模式，例如manual、paper或live。",
        "status": "接口调用结果状态。",
        "remote_order_id": "外部交易接口返回的订单ID；没有返回时为空。",
        "response_payload_json": "外部接口原始响应JSON。",
        "created_at": "接口下单尝试创建时间。",
    },
    "alpha_manual_fills": {
        "fill_id": "人工成交记录唯一ID。",
        "ticket_id": "关联的Alpha交易工单ID。",
        "operator_id": "录入成交的操作人标识。",
        "executed_quantity": "实际成交数量。",
        "executed_price": "实际成交价格。",
        "notes": "人工成交备注。",
        "created_at": "人工成交记录创建时间。",
    },
    "alpha_portfolio_snapshots": {
        "snapshot_id": "Alpha组合快照唯一ID。",
        "cash_balance": "快照时现金余额。",
        "realized_pnl": "截至快照时已实现盈亏。",
        "unrealized_pnl": "截至快照时未实现盈亏。",
        "nav": "快照时Alpha组合净值。",
        "created_at": "组合快照创建时间。",
    },
    "alpha_positions": {
        "symbol": "Alpha持仓标的代码。",
        "quantity": "当前持仓数量。",
        "avg_cost": "当前持仓平均成本。",
        "mark_price": "当前盯市价格。",
        "updated_at": "持仓最近更新时间。",
    },
    "alpha_reconciliation_runs": {
        "run_id": "对账运行唯一ID。",
        "source": "对账数据来源，例如manual或broker。",
        "status": "对账结果状态。",
        "discrepancies_json": "对账差异明细JSON。",
        "created_at": "对账运行创建时间。",
    },
    "alpha_tickets": {
        "ticket_id": "Alpha交易工单唯一ID。",
        "asset_symbol": "建议交易的资产代码。",
        "underlying_symbol": "研究或衍生品对应的底层标的代码。",
        "action": "交易方向，例如BUY或SELL。",
        "thesis": "交易理由或研究结论。",
        "suggested_quantity": "建议交易数量。",
        "suggested_limit_price": "建议限价。",
        "status": "工单状态，例如PROPOSED、APPROVED或FILLED。",
        "approved_by": "审批人标识；未审批时为空。",
        "expires_at": "工单过期时间。",
        "created_at": "工单创建时间。",
    },
    "alpha_watchlist_items": {
        "symbol": "研究观察标的代码。",
        "underlying_symbol": "对应底层标的代码。",
        "priority": "研究优先级，数值越小优先级越高。",
        "created_at": "观察项创建时间。",
    },
    "broker_events": {
        "event_id": "券商事件唯一ID。",
        "order_id": "关联订单ID，通常对应execution_orders.execution_order_id。",
        "event_type": "事件类型，例如SUBMITTED、FILLED或PARTIAL_FILL。",
        "payload_json": "事件载荷JSON，保存成交价、盈亏等扩展信息。",
        "created_at": "事件创建时间。",
    },
    "decision_input_snapshots": {
        "snapshot_id": "决策输入快照唯一ID。",
        "decision_run_id": "关联的决策运行ID。",
        "payload_json": "决策输入上下文JSON，包括行情、配置和运行模式。",
        "created_at": "快照创建时间。",
    },
    "decision_runs": {
        "decision_run_id": "决策运行唯一ID。",
        "symbol": "本次决策分析的标的代码。",
        "prompt_hash": "决策提示词或运行上下文的哈希，用于关联同一轮运行。",
        "model_name": "生成决策的模型名称；mock模式记录为mock模型。",
        "raw_output": "模型或策略返回的原始文本。",
        "parsed_action": "解析后的动作，例如BUY、SELL或HOLD。",
        "confidence": "决策置信度，范围0到100。",
        "target_position_ratio": "建议目标仓位比例。",
        "reason": "决策理由。",
        "created_at": "决策创建时间。",
    },
    "execution_orders": {
        "execution_order_id": "执行订单唯一ID。",
        "target_position_id": "关联目标仓位ID。",
        "symbol": "订单标的代码。",
        "action": "订单方向，例如BUY或SELL。",
        "quantity": "订单数量。",
        "limit_price": "订单限价或模拟成交参考价。",
        "status": "订单状态，例如READY、SUBMITTED或FILLED。",
        "broker_order_id": "券商返回的订单ID；模拟或未提交时为空。",
        "created_at": "订单创建时间。",
    },
    "execution_plans": {
        "plan_id": "执行计划唯一ID。",
        "symbol": "计划交易的标的代码。",
        "action": "计划动作，例如BUY、SELL或HOLD。",
        "target_value": "计划目标金额。",
        "reason": "计划生成原因。",
        "status": "计划状态，例如READY或ACKNOWLEDGED。",
        "created_at": "计划创建时间。",
    },
    "kill_switch_events": {
        "kill_switch_event_id": "停机事件唯一ID。",
        "active": "事件发生后停机开关是否处于激活状态。",
        "reason": "启用或解除停机的原因。",
        "created_at": "停机事件创建时间。",
    },
    "kill_switch_state": {
        "id": "固定主键，当前只使用1表示全局状态。",
        "active": "停机开关是否激活；激活后阻断交易动作。",
    },
    "risk_gate_events": {
        "risk_gate_event_id": "风控事件唯一ID。",
        "symbol": "被风控检查的标的代码。",
        "approved": "本次风控是否放行。",
        "rule_name": "触发或通过的风控规则名称。",
        "reason": "风控放行或拦截原因。",
        "created_at": "风控事件创建时间。",
    },
    "target_positions": {
        "target_position_id": "目标仓位唯一ID。",
        "decision_run_id": "关联的决策运行ID。",
        "symbol": "目标仓位标的代码。",
        "action": "目标动作，例如BUY或SELL。",
        "target_value": "目标仓位金额。",
        "target_position_ratio": "目标仓位占账户净值比例。",
        "status": "目标状态，例如ACTIVE或EXPIRED。",
        "expires_at": "目标仓位过期时间。",
        "created_at": "目标仓位创建时间。",
    },
    "us_watchlist": {
        "id": "自选股记录的自增主键。",
        "symbol": "美股代码，例如AAPL或MSFT。",
        "name": "股票名称，例如苹果或微软。",
        "sort_order": "列表排序值，数值越小展示越靠前。",
        "created_at": "记录创建时间。",
    },
    "user_preferences": {
        "key": "偏好项名称，例如dashboard。",
        "value": "偏好配置JSON字符串。",
        "updated_at": "偏好最近更新时间。",
    },
}


def _identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _qualified_table(table_name: str) -> str:
    return f"public.{_identifier(table_name)}"


def _literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    bind = op.get_bind()
    for table_name, comment in TABLE_COMMENTS.items():
        bind.exec_driver_sql(
            f"COMMENT ON TABLE {_qualified_table(table_name)} IS {_literal(comment)}"
        )
    for table_name, columns in COLUMN_COMMENTS.items():
        for column_name, comment in columns.items():
            bind.exec_driver_sql(
                f"COMMENT ON COLUMN {_qualified_table(table_name)}.{_identifier(column_name)} IS {_literal(comment)}"
            )


def downgrade() -> None:
    bind = op.get_bind()
    for table_name, columns in COLUMN_COMMENTS.items():
        for column_name in columns:
            bind.exec_driver_sql(
                f"COMMENT ON COLUMN {_qualified_table(table_name)}.{_identifier(column_name)} IS NULL"
            )
    for table_name in TABLE_COMMENTS:
        bind.exec_driver_sql(f"COMMENT ON TABLE {_qualified_table(table_name)} IS NULL")
