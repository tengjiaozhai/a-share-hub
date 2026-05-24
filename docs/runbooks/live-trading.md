# 实盘交易运行手册

## 前提条件

1. Phase 1-7 所有验收测试通过
2. 影子模式运行至少10个交易日
3. 无未对账订单
4. 紧急停止开关测试通过
5. 经纪商断连测试通过
6. 所有脚本通过fail-closed验证

## 影子模式脚本

### Fail-Closed设计原则

所有影子模式脚本都遵循fail-closed设计：
- 使用 `set -euo pipefail` 确保任何命令失败都导致脚本退出
- 不使用 `|| echo` 等错误忽略模式
- 使用 `REPO_ROOT` 变量而不是硬编码路径
- 实际执行CLI命令，不只检查模块导入

### 脚本列表

1. `scripts/run_shadow_cycle.sh` - 影子周期执行脚本
2. `scripts/run_reconcile.sh` - 对账执行脚本

### 运行影子周期

```bash
# 设置Python路径（可选，默认使用/opt/anaconda3/envs/py311/bin/python3）
export PYTHON=/path/to/python3

# 运行影子周期
./scripts/run_shadow_cycle.sh
```

### 运行对账

```bash
./scripts/run_reconcile.sh
```

### 故障排除

如果脚本失败：
1. 检查Python环境是否正确
2. 检查依赖是否安装
3. 检查网络连接（数据同步需要）
4. 查看详细错误信息（脚本会显示失败步骤）

## 启用实盘

1. 确认所有前提条件满足
2. 修改 `.env` 文件：`ENABLE_LIVE_TRADING=true`
3. 提交变更：`git commit -m "enable live trading"`
4. 部署到生产环境

## 监控要点

- 数据层：分钟线延迟、交易日历错误、多源差异
- 订单层：报单成功率、拒单率、撤单率
- 风险层：单日最大亏损、持仓集中度
- 合规层：程序化交易报备、策略版本管理

## 紧急停止

1. 调用 `/api/v1/kill-switch/activate` 端点
2. 或修改 `.env` 文件：`ENABLE_LIVE_TRADING=false`
3. 重启服务
