# Alpha Ledger And Reconciliation Runbook

1. 完成 Phase 1，确保 alpha ticket 和 manual fill 已可写入。
2. 通过组合重建接口或后台任务生成最新 alpha 组合快照。
3. 录入外部现金和持仓快照，运行 `/api/v1/alpha/reconciliation/run`。
4. 若返回 `MISMATCH`，在 dashboard 的 alpha 异常区确认差异并记录处理结论。
