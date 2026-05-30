#!/bin/bash
set -e

echo "启动 Crypto Hub..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

mkdir -p logs

nohup uvicorn src.main:app --host 0.0.0.0 --port 8000 > logs/app.log 2>&1 &

echo $! > .pid

echo "服务已启动，PID: $(cat .pid)"
