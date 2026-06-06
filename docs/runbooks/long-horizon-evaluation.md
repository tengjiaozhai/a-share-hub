# 长期 Shadow 评估指南

## 目标

长期评估只接受来自 `account_snapshots`、`execution_orders`、`broker_events`、`decision_runs` 的已落库证据。固定返回 0 的指标视为失败。

## 命令

```bash
/opt/anaconda3/envs/py311/bin/python3 -m src.main evaluate-shadow --window 1m
/opt/anaconda3/envs/py311/bin/python3 -m src.main evaluate-shadow --window 3m
/opt/anaconda3/envs/py311/bin/python3 -m src.main evaluate-shadow --window 1y
```

## 验收标准

- `status` 必须是 `ok`。
- `snapshot_count` 必须大于 0。
- `total_return` 必须从首尾净值计算。
- `max_drawdown` 必须从净值曲线计算。
- `fill_rate` 必须从 `execution_orders.status` 计算。
- `unreconciled_order_count` 必须来自对账状态。

## 失败处理

- 没有账户快照：先跑 paper 执行生成快照。
- 未对账订单大于 0：先运行 reconciliation，再重新评估。
- fill_rate 长期低于 0.95：停止推进实盘，检查行情、风控和执行服务。
