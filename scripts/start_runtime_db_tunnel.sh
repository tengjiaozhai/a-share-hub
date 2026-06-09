#!/usr/bin/env bash
# SSH 隧道启动脚本 — 将本地端口转发到 AWS PostgreSQL。
#
# 要求：
#   - .env 中配置 DATABASE_URL、AWS_HOST、AWS_SSH_USER、AWS_SSH_KEY_PATH
#   - 本地 DATABASE_URL 指向 127.0.0.1:<port>
#
# 用法：
#   bash scripts/start_runtime_db_tunnel.sh          # 前台运行
#   systemd 托管（见 deploy/systemd/）

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

# 加载 .env
if [[ -f "${REPO_ROOT}/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "${REPO_ROOT}/.env"
    set +a
fi

: "${AWS_SSH_KEY_PATH:?AWS_SSH_KEY_PATH not set}"
: "${AWS_SSH_USER:?AWS_SSH_USER not set}"
: "${AWS_HOST:?AWS_HOST not set}"

# 从 DATABASE_URL 提取本地监听端口
LOCAL_PORT="$(
  /opt/anaconda3/envs/py311/bin/python3 - <<'PY'
from src.storage.connection_url import extract_local_runtime_host_port
from src.core.config import Settings
_, port = extract_local_runtime_host_port(Settings().database_url)
print(port)
PY
)"

echo "Starting SSH tunnel: 127.0.0.1:${LOCAL_PORT} -> ${AWS_HOST}:127.0.0.1:5432"

exec ssh \
  -N \
  -i "${AWS_SSH_KEY_PATH}" \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=3 \
  -o StrictHostKeyChecking=accept-new \
  -L "127.0.0.1:${LOCAL_PORT}:127.0.0.1:5432" \
  "${AWS_SSH_USER}@${AWS_HOST}"
