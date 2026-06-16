# Dashboard Run Contract

## 1. Start run

### Request

`POST /api/v1/dashboard/runs`

```json
{
  "watchlist": ["MRVL", "NBIS", "NVDA", "AAPL", "MU"],
  "capital_base": 10000,
  "max_position_ratio": 0.2,
  "execution_mode": "full",
  "decision_mode": "real",
  "allow_new_positions": true
}
```

### Response

Status: `202 Accepted`

```json
{
  "run_context_id": "wrk-20260615-203007-5ddeec",
  "stream_url": "/api/v1/dashboard/runs/wrk-20260615-203007-5ddeec/events",
  "status": "accepted"
}
```

## 2. Stream events

### Route

`GET /api/v1/dashboard/runs/{run_context_id}/events`

### Event types

- `run.accepted`
- `stage.updated`
- `run.completed`
- `run.failed`

### SSE example

```text
event: stage.updated
data: {"run_context_id":"wrk-20260615-203007-5ddeec","seq":3,"event_type":"stage.updated","stage":"target","status":"done","payload":{"items":[{"symbol":"NVDA","target_quantity":4,"status":"ACTIVE"}],"duration_ms":18}}
```

## 3. Final snapshot

### Route

`GET /api/v1/dashboard/workbench?run_context_id={run_context_id}`

### Required fields

```json
{
  "latest_run": {
    "run_context_id": "wrk-20260615-203007-5ddeec",
    "steps": [],
    "run_pnl_summary": {
      "execution_fee_total": 0.36,
      "realized_pnl": 0.0,
      "unrealized_pnl": -0.60,
      "net_pnl": -0.96
    },
    "reconcile_items": [
      {
        "symbol": "NVDA",
        "quantity": 4,
        "avg_cost": 100.05,
        "mark_price": 99.90,
        "change_pct": -0.0015,
        "unrealized_pnl": -0.60,
        "fee_total": 0.12,
        "mark_time": "2026-06-15T20:30:38+08:00",
        "quote_status": "ok"
      }
    ]
  }
}
```

## 4. Reconciliation route

### Route

`GET /api/v1/reconciliation/status?run_context_id={run_context_id}`

### Rule

The payload returned here must match `latest_run.reconcile_items` for the same `run_context_id`.
