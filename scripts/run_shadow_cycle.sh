#!/usr/bin/env bash
# Shadow 交易日周期脚本 - 依赖真实 CLI 命令

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-/opt/anaconda3/envs/py311/bin/python3}"
SYMBOLS="${SYMBOLS:-600519.SH}"

echo "=== Starting Shadow Cycle ==="
echo "REPO_ROOT: ${REPO_ROOT}"
echo "PYTHON: ${PYTHON}"

cd "${REPO_ROOT}"

"${PYTHON}" -m alembic upgrade head

echo "Step 1: Running decisions..."
"${PYTHON}" -m src.main decide --symbols ${SYMBOLS} --mock-llm

echo "Step 2: Shadow execution..."
"${PYTHON}" -m src.main shadow-execute --symbols ${SYMBOLS} --mock-broker

echo "Step 3: Reconciling..."
"${PYTHON}" -m src.main reconcile --symbols ${SYMBOLS}

echo "Step 4: Long-horizon evaluation..."
"${PYTHON}" -m src.main evaluate-shadow --window 1m

echo "=== Shadow Cycle Complete ==="
