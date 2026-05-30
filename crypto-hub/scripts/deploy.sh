#!/bin/bash
set -e

echo "开始部署 Crypto Hub..."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "检查环境..."
python --version
pip --version

echo "安装依赖..."
pip install -r requirements.txt

echo "创建日志目录..."
mkdir -p logs

echo "启动服务..."
nohup uvicorn src.main:app --host 0.0.0.0 --port 8000 > logs/app.log 2>&1 &
echo $! > .pid

echo "部署完成! PID: $(cat .pid)"
