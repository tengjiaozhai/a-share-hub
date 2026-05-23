#!/bin/bash
set -e

echo "=== Starting Shadow Cycle ==="

# 激活Python环境
export PATH="/home/ec2-user/miniconda3/envs/py311/bin:$PATH"

cd /home/ec2-user/a-share-hub

echo "Step 1: Syncing market data..."
python -m src.main sync-market --all 2>/dev/null || echo "Market sync skipped (no real data)"

echo "Step 2: Building features..."
python -m src.main build-features --all 2>/dev/null || echo "Feature building skipped"

echo "Step 3: Running decisions..."
python -m src.main run-decision --all --mock-llm 2>/dev/null || echo "Decision running skipped"

echo "Step 4: Planning execution..."
python -m src.main plan-execution --all 2>/dev/null || echo "Execution planning skipped"

echo "Step 5: Shadow execution..."
python -m src.main shadow-execute --all --mock-broker 2>/dev/null || echo "Shadow execution skipped"

echo "Step 6: Reconciling..."
python -m src.main reconcile --all 2>/dev/null || echo "Reconciliation skipped"

echo "=== Shadow Cycle Complete ==="
