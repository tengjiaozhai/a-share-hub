#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-/opt/anaconda3/envs/py311/bin/python3}"

echo "=== Starting Reconciliation ==="
echo "REPO_ROOT: ${REPO_ROOT}"
echo "PYTHON: ${PYTHON}"

cd "${REPO_ROOT}"

"${PYTHON}" -m src.main reconcile --all

echo "=== Reconciliation Complete ==="
