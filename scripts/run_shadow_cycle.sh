#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-/opt/anaconda3/envs/py311/bin/python3}"

echo "=== Starting Shadow Cycle ==="
echo "REPO_ROOT: ${REPO_ROOT}"
echo "PYTHON: ${PYTHON}"

cd "${REPO_ROOT}"

"${PYTHON}" -m alembic upgrade head

echo "Step 1: Running decisions..."
"${PYTHON}" -m src.main decide --symbols 600519.SH --mock-llm

echo "Step 2: Shadow execution..."
"${PYTHON}" -m src.main shadow-execute --symbols 600519.SH --mock-broker

echo "Step 3: Reconciling..."
"${PYTHON}" -m src.main reconcile --symbols 600519.SH

echo "=== Shadow Cycle Complete ==="
