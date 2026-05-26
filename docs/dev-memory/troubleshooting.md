# 故障排除

## AWS 服务器缺少 psycopg3 导致 workbench 接口 500

**解决时间**: 2026-05-26  
**问题**: `GET /api/v1/dashboard/workbench` 返回 `Internal Server Error`，日志 `No module named 'psycopg'`

### 根本原因

`DATABASE_URL` 使用 `postgresql+psycopg://`（psycopg3 方言），服务器只装了 `psycopg2-binary`。

### 解决方案

```bash
~/miniconda3/envs/py311/bin/pip install psycopg[binary]
```

### 后续规则

- 部署新服务器时必须同时安装 `psycopg[binary]`（psycopg3）。
- `psycopg2-binary` 对应方言是 `postgresql+psycopg2://`，两者**不通用**。

---

## AWS 服务器旧进程缓存导致新代码不生效

**解决时间**: 2026-05-26  
**问题**: pip 安装新依赖后重启 uvicorn 仍然报 `ModuleNotFoundError`

### 根本原因

`killall python3` 只杀了部分进程，旧 uvicorn 子进程仍在运行，使用旧的进程内存。

### 可靠重启命令

```bash
ps aux | grep python | grep -v grep | awk '{print $2}' | xargs kill -9
sleep 3
nohup ~/miniconda3/envs/py311/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
```

---

## AWS 服务器缺少 httpx 导致 llm_client 导入失败

**解决时间**: 2026-05-26  
**问题**: uvicorn 启动失败，日志 `No module named 'httpx'`

### 解决方案

```bash
~/miniconda3/envs/py311/bin/pip install httpx
```

### 后续规则

`pyproject.toml` 的 `dependencies` 需显式列出 `httpx`，避免环境遗漏。

---

## SSH连接被拒绝

**解决时间**: 2026-05-23  
**问题**: SSH连接到远程服务器时提示"Permission denied"

### 原因

- 服务器配置为仅允许密码认证
- 需要使用sshpass工具传递密码

### 解决方案

```bash
sshpass -p '密码' ssh -o StrictHostKeyChecking=no root@服务器IP
```

---

## PostgreSQL连接失败

**解决时间**: 2026-05-23  
**问题**: 使用psql命令连接PostgreSQL时报错"command not found"

### 原因

- PostgreSQL客户端工具不在系统PATH中

### 解决方案

使用完整路径调用psql：

```bash
/www/server/pgsql/bin/psql -U douya -h localhost -d postgres
```

---

## conda Terms of Service错误

**解决时间**: 2026-05-23  
**问题**: 创建conda环境时报错"Terms of Service have not been accepted"

### 解决方案

```bash
/opt/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
/opt/miniconda3/bin/conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

---

## pyproject.toml构建后端错误

**解决时间**: 2026-05-23  
**问题**: pip安装时报错"Cannot import 'setuptools.backends._legacy'"

### 解决方案

使用正确的build-backend：

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"
```

---

## 服务器CPU/内存耗尽

**解决时间**: 2026-05-23  
**问题**: 安装依赖时服务器负载达到18+，CPU使用率85%+

### 解决方案

迁移到更高配置的服务器（AWS EC2 2核4GB）。

---

## GitHub SSH密钥认证失败

**解决时间**: 2026-05-24  
**问题**: git push时报错"Host key verification failed"

### 原因

- GitHub的主机密钥没有添加到known_hosts

### 解决方案

```bash
ssh-keyscan github.com >> ~/.ssh/known_hosts 2>/dev/null
```

---

## GitHub API密码认证失败

**解决时间**: 2026-05-24  
**问题**: 使用GitHub API创建仓库时报错"Requires authentication"

### 原因

- GitHub已停止支持密码认证API操作
- 需要使用Personal Access Token或SSH密钥

### 解决方案

使用SSH密钥认证：
1. 在服务器上生成SSH密钥：`ssh-keygen -t rsa -b 4096`
2. 将公钥添加到GitHub：https://github.com/settings/keys
3. 使用SSH方式克隆和推送

---

## AWS安全组端口未开放

**解决时间**: 2026-05-24  
**问题**: 无法从外部访问仪表盘（端口8000）

### 原因

- AWS EC2的8000端口未从外部开放

### 临时解决方案

使用SSH隧道：
```bash
ssh -i /Users/shenmingjie/.ssh/xingxing.pem -L 8000:localhost:8000 ec2-user@13.214.201.113
# 浏览器访问: http://localhost:8000/dashboard
```

### 永久解决方案

在AWS控制台开放8000端口入站规则。

---

## uvicorn服务启动失败

**解决时间**: 2026-05-24  
**问题**: uvicorn服务启动后无法访问

### 原因

- 服务启动命令超时
- 可能是端口被占用

### 解决方案

```bash
# 杀死现有进程
pkill -f uvicorn

# 重新启动服务
cd /home/ec2-user/a-share-hub
nohup ~/miniconda3/envs/py311/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
```
