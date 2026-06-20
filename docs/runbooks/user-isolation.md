# User Isolation

## Authentication

- Login uses the signed `access_token` HttpOnly Cookie.
- Token expiry and Cookie `Max-Age` are both `AUTH_SESSION_HOURS=168` (7 days).
- Public registration always creates role `user`.
- Administrators are assigned explicitly with:
  `/opt/anaconda3/envs/py311/bin/python3 -m src.main set-user-role --user-id <id> --role admin`.

## Tenant Boundary

- HTTP user identity comes only from `get_current_user_id`.
- User-owned Stores require `TenantContext` at construction.
- Store methods never accept a second user ID and never fall back to `system`.
- CLI, scheduler, and backfill use `SYSTEM_TENANT` explicitly.
- Cross-user relationships are checked by Store queries in the write transaction; this project intentionally does not use foreign keys.

## Global State

- `kill_switch_state` is global.
- `kill_switch_events` is global and records `actor_user_id`.
- `scheduled_job_locks` is global.
- Broker callback authentication is global HMAC ingress, but accepted `broker_events` are owned by the user resolved from `execution_orders`.

## Verification

Run the focused security tests after any change in this area:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q \
  tests/test_auth_security.py \
  tests/test_auth_routes.py \
  tests/test_route_authentication.py \
  tests/test_broker_event_isolation.py \
  tests/test_user_isolation.py \
  tests/test_alpha_runtime_store.py \
  tests/test_paper_ledger_store.py \
  tests/test_kill_switch_api.py
```

## Operational Notes

- Schema migration `20260620_000016_harden_user_isolation.py` adds `broker_events.user_id` (backfilled from `execution_orders`, fail-fast on orphan rows) and `kill_switch_events.actor_user_id` (nullable, no backfill). It replaces the `alpha_watchlist_items` primary key with `(user_id, symbol)`. No foreign keys are introduced.
- The legacy migration files `000013` and `000014` retain `server_default=SYSTEM_USER_ID` because historical rows used it; new writes must supply an explicit tenant.