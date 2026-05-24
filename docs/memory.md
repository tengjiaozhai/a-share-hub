# 工作区记忆

## 语言偏好

- **思考过程**: 中文
- **代码注释**: 英文
- **提交信息**: 英文
- **文档**: 中文

## 开发环境

### Python环境

- **版本**: Python 3.11
- **管理工具**: Miniconda
- **调用方式**: 使用完整路径避免自动激活
- **路径**: `/home/ec2-user/miniconda3/envs/py311/bin/python`

### 数据库

- **主数据库**: PostgreSQL 15.16
- **连接**: `postgresql://douya:douya@localhost:5432/douya`

### 服务器

- **IP**: 13.214.201.113
- **用户**: ec2-user
- **配置**: 2核4GB内存
- **操作系统**: Amazon Linux 2023
- **区域**: ap-southeast-1 (新加坡)

## 项目约定

### 代码风格

- 遵循PEP 8
- 使用类型注解
- 优先使用标准库
- 最小化依赖

### 测试策略

- 测试驱动开发（TDD）
- 每个阶段必须有验收测试
- 测试覆盖率要求：80%+
- **当前测试数**: 65个

### 提交规范

- 使用语义化提交信息
- 每个功能一个提交
- 提交前必须通过测试

## 工具偏好

### 命令行工具

- **SSH**: 使用SSH密钥进行连接
- **文件传输**: 使用scp或rsync
- **进程管理**: 使用systemd

### 编辑器/IDE

- **主要**: OpenCode CLI
- **辅助**: VS Code（远程开发）

## 项目状态

### 当前阶段

- **项目**: A股自动交易系统
- **状态**: Phase 1-8 已完成
- **下一步**: 影子模式验证 + Windows执行节点部署

### 已完成

1. ✅ 环境评估
2. ✅ 服务器配置（AWS EC2 2核4GB）
3. ✅ Python 3.11环境
4. ✅ PostgreSQL数据库
5. ✅ 项目目录结构
6. ✅ Phase 1-8 全部完成
7. ✅ 65个测试全部通过
8. ✅ GitHub代码同步
9. ✅ 仪表盘创建

### 待完成

1. ⏸️ 影子模式验证（需要配置LLM API）
2. ⏸️ Windows执行节点部署
3. ⏸️ QMT实盘连接
4. ⏸️ AWS安全组端口开放

## GitHub同步

### 仓库信息

- **地址**: https://github.com/tengjiaozhai/a-share-hub
- **认证**: SSH密钥
- **分支**: master

### 同步流程

```bash
# 服务器推送
cd /home/ec2-user/a-share-hub
git add .
git commit -m "描述"
git push origin master

# 本地拉取
cd ~/workSpace/tranding/a-share-hub
git pull origin master
```

## 仪表盘

### 访问方式

- **本地访问**: http://localhost:8000/dashboard（需SSH隧道）
- **公网访问**: http://13.214.201.113:8000/dashboard（需开放端口）

### 文件位置

- **前端页面**: `src/api/dashboard.html`
- **后端路由**: `src/api/routes_dashboard.py`

## 学习记录

### 服务器资源管理

- 2核2GB服务器无法运行完整的量化交易系统
- conda自动激活会消耗额外资源
- 需要预留30%+资源余量应对峰值负载

### Git同步

- GitHub已停止支持密码认证API操作
- 需要使用SSH密钥认证
- ssh-keyscan github.com 添加主机密钥

### 影子模式

- 影子模式 = 系统正常运行，但不真正下单
- 用于验证策略和测试系统
- 符合监管要求（程序化交易先报告、后交易）

## 参考资源

### 文档

- [阶段计划](docs/superpowers/plans/2026-05-23-a-share-auto-trading-phases.md)
- [可行性评估](evalution.md)
- [研究报告](deep-research-report%20(1).md)
- [实盘运行手册](docs/runbooks/live-trading.md)
- [项目完成记录](docs/dev-memory/completion-record.md)

### 工具

- [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [GitHub](https://github.com)
