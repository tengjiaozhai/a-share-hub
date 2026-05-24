#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-/opt/anaconda3/envs/py311/bin/python3}"

echo "=== Starting Shadow Cycle ==="
echo "REPO_ROOT: ${REPO_ROOT}"
echo "PYTHON: ${PYTHON}"

cd "${REPO_ROOT}"

echo "Step 1: Syncing market data..."
"${PYTHON}" -m src.main sync-market --all

echo "Step 2: Building features..."
"${PYTHON}" -m src.main build-features --all

echo "Step 3: Running decisions..."
"${PYTHON}" -m src.main run-decision --all --mock-llm

echo "Step 4: Planning execution..."
"${PYTHON}" -m src.main plan-execution --all

echo "Step 5: Shadow execution..."
"${PYTHON}" -m src.main shadow-execute --all --mock-broker

echo "Step 6: Reconciling..."
"${PYTHON}" -m src.main reconcile --all

echo "=== Shadow Cycle Complete ==="
