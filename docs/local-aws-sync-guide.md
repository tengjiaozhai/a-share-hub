# 本地与AWS服务器代码同步操作手册

## 概述

本手册介绍如何在本地开发环境和AWS服务器之间同步代码。

## 服务器信息

| 项目 | 值 |
|------|-----|
| 服务器IP | 13.214.201.113 |
| SSH用户 | ec2-user |
| SSH密钥 | /Users/shenmingjie/.ssh/xingxing.pem |
| 项目路径 | /home/ec2-user/a-share-hub |
| Python环境 | /home/ec2-user/miniconda3/envs/py311 |

## 本地推送代码

### 1. 检查本地状态

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git status
```

### 2. 添加更改

```bash
# 添加所有更改
git add .

# 或添加特定文件
git add .env .env.example .gitignore src/ tests/
```

### 3. 提交更改

```bash
git commit -m "描述性提交信息"
```

### 4. 推送到远程仓库

```bash
git push origin master
```

## AWS服务器拉取代码

### 1. 登录服务器

```bash
ssh -i /Users/shenmingjie/.ssh/xingxing.pem ec2-user@13.214.201.113
```

### 2. 进入项目目录

```bash
cd /home/ec2-user/a-share-hub
```

### 3. 检查服务器状态

```bash
git status
```

### 4. 拉取远程更新

```bash
git pull origin master
```

### 5. 如果有本地冲突

```bash
# 恢复本地更改
git restore src/main.py

# 清理缓存文件
rm -f src/__pycache__/*.pyc

# 重新拉取
git pull origin master
```

## 安装依赖

### 1. 激活Python环境

```bash
conda activate py311
```

### 2. 安装项目依赖

```bash
cd /home/ec2-user/a-share-hub
pip install -e ".[dev]"
```

### 3. 运行数据库迁移

```bash
python -m alembic upgrade head
```

## 运行测试

```bash
cd /home/ec2-user/a-share-hub
python -m pytest -q
```

## 启动服务

### 启动API服务

```bash
cd /home/ec2-user/a-share-hub
python -m src.main serve
```

### 运行影子周期

```bash
bash scripts/run_shadow_cycle.sh
```

### 运行对账

```bash
bash scripts/run_reconcile.sh
```

## 常见问题

### 问题1: git pull失败

**错误信息:**
```
error: Your local changes to the following files would be overwritten by merge
```

**解决方案:**
```bash
# 恢复本地更改
git restore <冲突文件>

# 或者暂存本地更改
git stash
git pull origin master
git stash pop
```

### 问题2: 依赖安装失败

**解决方案:**
```bash
# 更新pip
pip install --upgrade pip

# 重新安装依赖
pip install -e ".[dev]" --force-reinstall
```

### 问题3: 数据库连接失败

**检查步骤:**
```bash
# 检查PostgreSQL状态
sudo systemctl status postgresql

# 检查Redis状态
sudo systemctl status redis

# 测试数据库连接
psql -h localhost -U douya -d douya
```

### 问题4: 端口被占用

**解决方案:**
```bash
# 查找占用端口的进程
lsof -i :8000

# 终止进程
kill <PID>
```

## 环境变量配置

### .env文件位置

```bash
/home/ec2-user/a-share-hub/.env
```

### 关键配置项

```bash
# 数据库
DATABASE_URL=postgresql+psycopg://douya:douya@localhost:5432/douya

# Redis
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
REDIS_ROLE=cache

# 服务器
AWS_HOST=13.214.201.113
AWS_SSH_USER=ec2-user
AWS_SSH_KEY_PATH=/home/ec2-user/xingxing.pem
```

## 快速参考

| 操作 | 命令 |
|------|------|
| 登录服务器 | `ssh -i xingxing.pem ec2-user@13.214.201.113` |
| 进入项目 | `cd /home/ec2-user/a-share-hub` |
| 拉取更新 | `git pull origin master` |
| 安装依赖 | `pip install -e ".[dev]"` |
| 运行迁移 | `python -m alembic upgrade head` |
| 启动服务 | `python -m src.main serve` |
| 运行测试 | `python -m pytest -q` |