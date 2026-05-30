#!/bin/bash
set -e

echo "停止 Crypto Hub..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

if [ -f .pid ]; then
    PID=$(cat .pid)
    if ps -p $PID > /dev/null; then
        kill $PID
        echo "服务已停止，PID: $PID"
    else
        echo "服务未运行"
    fi
    rm -f .pid
else
    echo "PID文件不存在"
fi
