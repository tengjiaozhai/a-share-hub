# AWS PostgreSQL SSH 隧道运维手册

## 必需的 .env 字段

```dotenv
DATABASE_URL=postgresql+psycopg://douya:change_me@127.0.0.1:15432/douya
AWS_HOST=13.214.201.113
AWS_SSH_USER=ec2-user
AWS_SSH_KEY_PATH=/home/ops/.ssh/aws-a-share-hub.pem
```

`DATABASE_URL` **必须**指向本机 loopback（`127.0.0.1` 或 `localhost`），由 SSH 隧道转发到 AWS。不允许直连国外数据库地址。

---

## 手工启动隧道

```bash
cd /opt/a-share-hub
bash scripts/start_runtime_db_tunnel.sh
```

进程会前台阻塞，保持隧道活跃。`Ctrl+C` 停止。

验证本地端口已监听：

```bash
ss -tlnp | grep 15432
```

---

## 安装 systemd 服务

```bash
sudo cp deploy/systemd/a-share-hub-runtime-db-tunnel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now a-share-hub-runtime-db-tunnel
```

查看状态：

```bash
sudo systemctl status a-share-hub-runtime-db-tunnel
sudo journalctl -u a-share-hub-runtime-db-tunnel -f
```

---

## 验证数据库连通性

```bash
/opt/anaconda3/envs/py311/bin/python3 scripts/check_runtime_db.py
```

预期输出（成功）：

```
ok latency_ms=3.21
```

预期输出（失败）：

```
error latency_ms=5002.00 detail=...
```

退出码：`0` = 成功，`1` = 失败。

---

## 验证 Readiness API

```bash
curl -s http://127.0.0.1:8000/health/ready
```

成功时返回 `200`：

```json
{"status": "ok", "latency_ms": 3.21}
```

失败时返回 `503`：

```json
{"detail": {"ok": false, "latency_ms": 5002.0, "error": "..."}}
```

---

## 排障

### 503 on /health/ready

1. 检查隧道进程是否存活：`sudo systemctl status a-share-hub-runtime-db-tunnel`
2. 检查本地端口：`ss -tlnp | grep 15432`
3. 手工测试隧道：`psql -h 127.0.0.1 -p 15432 -U douya -d douya -c "SELECT 1"`
4. 检查 SSH 密钥权限：`ls -la /home/ops/.ssh/aws-a-share-hub.pem`（应为 `600`）

### 隧道频繁断开

- `ServerAliveInterval=15` 和 `ServerAliveCountMax=3` 已配置
- systemd `Restart=always` + `RestartSec=5` 会自动重连
- 检查网络质量：`ping ${AWS_HOST}`

### DATABASE_URL 不是 loopback

如果看到错误 `runtime DATABASE_URL must use loopback host`，说明 `.env` 中的 `DATABASE_URL` 指向了远程地址。修正为 `127.0.0.1:<port>`。

### 重启隧道

```bash
sudo systemctl restart a-share-hub-runtime-db-tunnel
```

### 查看日志

```bash
sudo journalctl -u a-share-hub-runtime-db-tunnel --since "10 min ago"
```
