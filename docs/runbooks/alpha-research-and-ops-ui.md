# Alpha Research And Ops UI Runbook

1. 维护观察列表。
2. 通过 `/api/v1/alpha/research/scan` 生成候选。
3. 检查候选分数和原因。
4. 通过 `/api/v1/alpha/research/propose-top-ticket` 将候选转成建议单。
5. 回到 Phase 1 的 ticket/fill 流程继续执行。