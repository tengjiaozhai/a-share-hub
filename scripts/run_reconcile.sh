#!/bin/bash
set -e

echo "=== Starting Reconciliation ==="

export PATH="/home/ec2-user/miniconda3/envs/py311/bin:$PATH"

cd /home/ec2-user/a-share-hub

python -m src.main reconcile --all 2>/dev/null || echo "Reconciliation completed with warnings"

echo "=== Reconciliation Complete ==="
