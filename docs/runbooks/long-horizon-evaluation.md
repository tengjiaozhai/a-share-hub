# 长期评估指南

## 命令

- 月度评估：`python -m src.main evaluate-shadow --window 1m`
- 季度评估：`python -m src.main evaluate-shadow --window 3m`
- 年度评估：`python -m src.main evaluate-shadow --window 1y`

## 指标说明

- `total_return`：区间总收益率
- `max_drawdown`：最大回撤
- `turnover`：换手率
- `decision_count`：决策次数
- `fill_rate`：成交率
- `unreconciled_order_count`：未对账订单数
