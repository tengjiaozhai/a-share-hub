#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

START_RESPONSE="$(curl -s -X POST "$BASE_URL/api/v1/dashboard/runs" \
  -H 'Content-Type: application/json' \
  --data '{"watchlist":["NVDA","AAPL"],"capital_base":10000,"max_position_ratio":0.2,"execution_mode":"full","decision_mode":"real","allow_new_positions":true}')"

RUN_CONTEXT_ID="$(python3 - <<'PY' "$START_RESPONSE"
import json
import sys

payload = json.loads(sys.argv[1])
print(payload["run_context_id"])
PY
)"

echo "run_context_id=$RUN_CONTEXT_ID"

curl -sN "$BASE_URL/api/v1/dashboard/runs/${RUN_CONTEXT_ID}/events" | python3 - <<'PY'
import json
import sys

for raw_line in sys.stdin:
    line = raw_line.strip()
    if not line.startswith("data: "):
        continue
    payload = json.loads(line[6:])
    print(f"{payload['seq']} {payload['event_type']} {payload['stage']} {payload['status']}")
    if payload["event_type"] == "run.completed":
        break
PY

curl -s "$BASE_URL/api/v1/dashboard/workbench?run_context_id=${RUN_CONTEXT_ID}" | python3 - <<'PY'
import json
import sys

payload = json.load(sys.stdin)
summary = payload["latest_run"]["run_pnl_summary"]
print(f"net_pnl={summary['net_pnl']}")
print(f"reconcile_count={len(payload['latest_run']['reconcile_items'])}")
PY
