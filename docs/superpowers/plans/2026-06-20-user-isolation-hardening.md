# User Isolation Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden user isolation across authentication, storage, broker events, Alpha watchlists, dashboards, and paper ledgers while retaining the existing signed Cookie token architecture with a fixed seven-day lifetime and adding no foreign keys.

**Architecture:** Replace request-path prefix authorization with router-level FastAPI dependencies, bind user-owned stores to an immutable `TenantContext`, and move genuinely global operations into a separate `SystemRuntimeStore`. Broker callbacks remain HMAC-authenticated but derive their tenant from the server-owned execution order. Database migrations add tenant columns, composite keys, and indexes only; they intentionally add no foreign keys.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL/SQLite test adapters, pytest

---

## Scope Decisions

- Keep the existing HMAC-signed Cookie token. Do not introduce JWT libraries, refresh tokens, server-side sessions, or parallel authentication paths.
- Set both token expiry and Cookie `Max-Age` to seven days (`604800` seconds) through the existing `auth_session_hours=168` setting.
- Add no foreign keys. Cross-user consistency is enforced by tenant-bound stores, server-side ownership lookup, affected-row checks, and two-user tests.
- Keep `kill_switch_state`, `scheduled_job_locks`, and the broker callback ingress global. `broker_events` themselves become user-owned after the callback resolves the execution order owner.
- Remove the username-based admin grant. Public registration always creates `role="user"`; role elevation uses an explicit CLI command.
- Migrate in place. Delete `runtime_store_v2.py` and remove old optional/default user paths in the same change; do not keep compatibility wrappers.

## Success Criteria

1. A login token is valid immediately, invalid at seven days, and its Cookie has `Max-Age=604800`.
2. Public registration cannot create an administrator for any username.
3. Every protected API router declares authentication as a FastAPI dependency; adding a route under that router cannot accidentally make it public.
4. Broker callbacks do not require a login Cookie, reject unknown orders, derive `user_id` from an execution order, and never trust tenant fields from payloads.
5. Dashboard events, reconciliation counts, and daily PnL contain only the current user's broker events.
6. Two users can add the same Alpha symbol independently.
7. User-owned stores are constructed with a non-empty tenant and expose no method that accepts a second arbitrary `user_id`.
8. User writes cannot silently fall back to `system`; CLI and scheduler code use an explicit system tenant.
9. Cross-user read, update, delete, Alpha watchlist, paper ledger, broker event, and dashboard tests pass.
10. The full test suite, Ruff, MyPy, and Alembic upgrade checks pass.

## File Map

| File | Responsibility after migration |
| --- | --- |
| `src/core/tenant.py` | Immutable validated `TenantContext` and canonical `SYSTEM_TENANT` |
| `src/core/config.py` | Existing seven-day authentication lifetime setting |
| `src/api/auth_security.py` | Cookie signing/parsing and request principal population only |
| `src/api/dependencies.py` | Router authentication dependency and tenant-bound Store construction |
| `src/api/routes_auth.py` | Registration/login; registration always creates a normal user |
| `src/main.py` | CLI role administration and explicit system Store construction |
| `src/storage/runtime_store.py` | User-owned runtime operations bound to one `TenantContext` |
| `src/storage/system_runtime_store.py` | Global Kill Switch, lock-independent system operations, and broker owner resolution |
| `src/storage/dependencies.py` | Engine singleton only; no unauthenticated user Store singleton |
| `src/storage/models.py` | Tenant-owned broker events and composite Alpha watchlist primary key |
| `src/paper_ledger/store.py` | Paper ledger Store bound to one tenant |
| `src/a_stock/watchlist.py` | A-share watchlist Store bound to one tenant using `TenantContext` |
| `src/us_stock/watchlist.py` | US watchlist Store bound to one tenant using `TenantContext` |
| `alembic/versions/20260620_000016_harden_user_isolation.py` | In-place schema migration without foreign keys |
| `tests/test_auth_security.py` | Seven-day token boundary tests |
| `tests/test_auth_routes.py` | Cookie lifetime and registration-role tests |
| `tests/test_route_authentication.py` | Router-level authentication coverage |
| `tests/test_broker_event_isolation.py` | Broker owner derivation and tenant isolation |
| `tests/test_user_isolation.py` | Cross-user Store and dashboard isolation |
| `tests/test_alpha_runtime_store.py` | Same-symbol Alpha watchlist isolation |
| `tests/test_paper_ledger_store.py` | Tenant-bound paper ledger update/read isolation |
| `.env.example` | Documents the seven-day session setting |
| `docs/runbooks/user-isolation.md` | Operational model, global tables, role elevation, and verification |

### Task 1: Lock the Existing Authentication Token to Seven Days

**Files:**
- Modify: `src/core/config.py:40-44`
- Modify: `src/api/auth_security.py:62-80`
- Modify: `src/api/routes_auth.py:98-110`
- Create: `tests/test_auth_security.py`
- Create: `tests/test_auth_routes.py`
- Modify: `.env.example`

- [ ] **Step 1: Write token-boundary tests**

Create `tests/test_auth_security.py`:

```python
from unittest.mock import patch

from src.api.auth_security import create_auth_token, read_auth_token
from src.core.config import Settings


def test_auth_session_defaults_to_seven_days():
    assert Settings(_env_file=None).auth_session_hours == 168


def test_auth_token_expires_at_seven_day_boundary():
    settings = Settings(_env_file=None, auth_secret_key="test-secret", auth_session_hours=168)
    issued_at = 1_800_000_000

    with patch("src.api.auth_security.time.time", return_value=issued_at):
        token = create_auth_token("usr-1", settings)

    with patch("src.api.auth_security.time.time", return_value=issued_at + 604_799):
        assert read_auth_token(token, settings) == "usr-1"

    with patch("src.api.auth_security.time.time", return_value=issued_at + 604_800):
        assert read_auth_token(token, settings) is None
```

Create `tests/test_auth_routes.py` with the Cookie assertion:

```python
from src.api.routes_auth import _login_response


def test_login_cookie_uses_seven_day_max_age(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-secret")
    monkeypatch.setenv("AUTH_SESSION_HOURS", "168")

    response = _login_response(
        {"user_id": "usr-1", "username": "alice", "email": "alice@example.com", "role": "user"},
        "/dashboard",
        True,
    )

    cookie = response.headers["set-cookie"]
    assert "Max-Age=604800" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
```

- [ ] **Step 2: Run the tests and confirm the exact expiry boundary fails**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_auth_security.py tests/test_auth_routes.py 2>&1 | head -c 4000
```

Expected: the boundary test fails because the existing implementation accepts a token when `exp == now`.

- [ ] **Step 3: Make expiry semantics explicit and retain the existing setting**

Change `read_auth_token` in `src/api/auth_security.py`:

```python
    if int(data.get("exp", 0)) <= int(time.time()):
        return None
```

Keep the canonical configuration in `src/core/config.py`:

```python
    auth_session_hours: int = 168
```

Add this block to `.env.example` after `EXECUTION_MODE`:

```dotenv
# 登录 Cookie 与签名 token 均在 7 天后过期
AUTH_SECRET_KEY=change_me
AUTH_COOKIE_NAME=access_token
AUTH_COOKIE_SECURE=false
AUTH_SESSION_HOURS=168
```

- [ ] **Step 4: Run the focused tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_auth_security.py tests/test_auth_routes.py 2>&1 | head -c 4000
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/config.py src/api/auth_security.py src/api/routes_auth.py tests/test_auth_security.py tests/test_auth_routes.py .env.example
git commit -m "test: lock auth sessions to seven days"
```

### Task 2: Remove Username-Based Administrator Grants

**Files:**
- Modify: `src/api/routes_auth.py:35-57`
- Modify: `src/storage/auth_store.py:9-57`
- Modify: `src/main.py`
- Modify: `tests/test_auth_routes.py`
- Create: `tests/test_admin_role_cli.py`

- [ ] **Step 1: Add failing registration and role-management tests**

Append to `tests/test_auth_routes.py`:

```python
def test_registration_never_grants_admin(authenticated_app, monkeypatch):
    created: dict[str, str] = {}

    class FakeAuthStore:
        def get_user_by_account(self, account: str):
            return None

        def create_user(self, username: str, email: str, password_hash: str, role: str):
            created["role"] = role
            return {
                "user_id": "usr-new",
                "username": username,
                "email": email,
                "role": role,
            }

    monkeypatch.setattr("src.api.routes_auth._auth_store", FakeAuthStore)
    client = TestClient(authenticated_app)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "tengjiaozhai",
            "email": "admin-attempt@example.com",
            "password": "password-123",
            "confirm_password": "password-123",
        },
    )

    assert response.status_code == 200
    assert created["role"] == "user"
```

Create `tests/test_admin_role_cli.py`:

```python
from sqlalchemy import create_engine

from src.storage.auth_models import AppUserRow
from src.storage.auth_store import AuthStore
from src.storage.models import Base


def test_set_role_requires_existing_user_and_allowed_role(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/auth.db", future=True)
    Base.metadata.create_all(engine)
    store = AuthStore(engine)
    user = store.create_user("alice", "alice@example.com", "hash", "user")

    assert store.set_role(user["user_id"], "admin") is True
    assert store.get_user(user["user_id"])["role"] == "admin"
    assert store.set_role("missing", "admin") is False
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_auth_routes.py tests/test_admin_role_cli.py 2>&1 | head -c 4000
```

Expected: registration returns `admin` for the reserved username and `AuthStore.set_role` does not exist.

- [ ] **Step 3: Make registration always create a normal user**

Replace the role selection in `src/api/routes_auth.py`:

```python
    user = store.create_user(username, email, hash_password(password), role="user")
```

Add to `AuthStore`:

```python
    def set_role(self, user_id: str, role: str) -> bool:
        if role not in {"user", "admin"}:
            raise ValueError(f"unsupported role: {role}")
        with self.engine.begin() as conn:
            result = conn.execute(
                AppUserRow.__table__.update()
                .where(AppUserRow.user_id == user_id)
                .values(role=role)
            )
        return result.rowcount == 1
```

Add a `set-user-role` CLI parser and handler in `src/main.py` using the existing parser style. At this task boundary, reuse the current canonical `get_runtime_store().engine`; Task 4 will replace it with the engine-only accessor when the Store dependency is migrated:

```python
role_parser = subparsers.add_parser("set-user-role")
role_parser.add_argument("--user-id", required=True)
role_parser.add_argument("--role", required=True, choices=("user", "admin"))
```

The handler must use the configured engine and fail fast:

```python
elif args.command == "set-user-role":
    store = AuthStore(get_runtime_store().engine)
    if not store.set_role(args.user_id, args.role):
        raise SystemExit(f"user not found: {args.user_id}")
    print(f"updated {args.user_id} role to {args.role}")
```

- [ ] **Step 4: Run auth and CLI tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_auth_routes.py tests/test_admin_role_cli.py tests/test_cli_new.py 2>&1 | head -c 6000
```

Expected: all tests pass and no source match remains for the hardcoded administrator:

```bash
rg -n 'tengjiaozhai|username ==.*admin' src tests 2>&1 | head -c 4000
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add src/api/routes_auth.py src/storage/auth_store.py src/main.py tests/test_auth_routes.py tests/test_admin_role_cli.py
git commit -m "fix: make administrator grants explicit"
```

### Task 3: Make Router Dependencies the Authentication Authority

**Files:**
- Modify: `src/api/auth_security.py:16-41,97-116`
- Modify: `src/api/routes_alpha.py`
- Modify: `src/api/routes_crypto.py`
- Modify: `src/api/routes_dashboard.py`
- Modify: `src/api/routes_decision_runs.py`
- Modify: `src/api/routes_execution_plans.py`
- Modify: `src/api/routes_kill_switch.py`
- Modify: `src/api/routes_market.py`
- Modify: `src/api/routes_portfolio_targets.py`
- Modify: `src/api/routes_reconciliation.py`
- Modify: `src/a_stock/routes.py`
- Modify: `src/us_stock/routes.py`
- Modify: `tests/unit/test_decision_run_repository_integration.py`
- Modify: `tests/us_stock/test_routes.py`
- Create: `tests/test_route_authentication.py`

- [ ] **Step 1: Add route-boundary tests**

Create `tests/test_route_authentication.py`:

```python
from fastapi.testclient import TestClient


PROTECTED_GETS = (
    "/api/v1/dashboard/workbench",
    "/api/v1/market/stocks",
    "/api/v1/alpha/portfolio",
    "/api/v1/us-stock/watchlist",
    "/api/v1/a-stock/watchlist",
    "/api/v1/decision-runs",
    "/api/v1/execution-plans/ready",
    "/api/v1/portfolio-targets/active",
    "/api/v1/reconciliation/status",
    "/api/v1/kill-switch/status",
    "/api/v1/crypto/status",
)


def test_protected_routers_reject_anonymous_requests(test_app):
    client = TestClient(test_app)
    for path in PROTECTED_GETS:
        assert client.get(path).status_code == 401, path


def test_broker_callback_is_not_cookie_authenticated(test_app):
    client = TestClient(test_app)
    response = client.post("/api/v1/broker-events", content=b"{}")
    assert response.status_code != 401 or response.json()["detail"] == "invalid broker signature"
```

- [ ] **Step 2: Run the test and verify that protection currently depends on middleware paths**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_route_authentication.py 2>&1 | head -c 4000
```

Expected: the broker callback is rejected before HMAC handling because `/api/v1/broker-events` is in `PROTECTED_PREFIXES`.

- [ ] **Step 3: Put authentication on each protected router**

For every protected router, use this canonical form:

```python
from fastapi import APIRouter, Depends

from src.api.dependencies import get_current_user

router = APIRouter(
    prefix="/api/v1/dashboard",
    dependencies=[Depends(get_current_user)],
)
```

Apply the dependency to the Alpha, Crypto, Dashboard API, Decision Runs, Execution Plans, Kill Switch, Market, Portfolio Targets, Reconciliation, A-share, and US-share routers. Keep endpoint-level `Depends(get_current_user_id)` wherever the endpoint needs the actual tenant identifier.

For the mixed Dashboard module, keep `/dashboard` HTML redirection in middleware and put `Depends(get_current_user)` directly on every `/api/v1/dashboard/*` endpoint if changing the router prefix would alter existing URLs.

Do not add Cookie authentication to `routes_broker_events.py`; HMAC is its only driving-adapter authentication.

- [ ] **Step 4: Reduce middleware to principal loading and HTML redirect behavior**

Delete `PROTECTED_PREFIXES` and `_is_protected_path`. Keep middleware behavior limited to:

```python
async def auth_middleware(request: Request, call_next):
    user = get_current_user_from_request(request)
    request.state.user = user

    if request.url.path in {"/login", "/register"} and user:
        return RedirectResponse("/dashboard", status_code=303)
    if request.url.path == "/dashboard" and not user:
        return RedirectResponse("/login?next=/dashboard", status_code=303)
    return await call_next(request)
```

- [ ] **Step 5: Repair stale tests to authenticate through the normal dependency**

In `tests/unit/test_decision_run_repository_integration.py`, override both dependencies used by middleware/router construction:

```python
from src.api.dependencies import get_current_user, get_current_user_id

app.dependency_overrides[get_current_user] = lambda: {
    "user_id": TEST_USER_ID,
    "username": "test-user",
    "email": "test@example.com",
    "role": "user",
}
app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
```

In `tests/us_stock/test_routes.py`, use the repository's `authenticated_client` fixture instead of a module-level anonymous `TestClient`.

- [ ] **Step 6: Run route and existing API tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_route_authentication.py tests/unit/test_decision_run_repository_integration.py tests/us_stock/test_routes.py tests/test_alpha_routes.py tests/test_dashboard_api.py 2>&1 | head -c 10000
```

Expected: all tests pass; anonymous protected requests return 401; broker callbacks reach HMAC validation.

- [ ] **Step 7: Commit**

```bash
git add src/api src/a_stock/routes.py src/us_stock/routes.py tests/test_route_authentication.py tests/unit/test_decision_run_repository_integration.py tests/us_stock/test_routes.py
git commit -m "refactor: enforce authentication at router boundaries"
```

### Task 4: Introduce a Canonical Tenant Context and Bind Stores

**Files:**
- Create: `src/core/tenant.py`
- Modify: `src/storage/runtime_store.py`
- Create: `src/storage/system_runtime_store.py`
- Modify: `src/storage/dependencies.py`
- Modify: `src/api/dependencies.py`
- Modify: `src/paper_ledger/store.py`
- Modify: `src/a_stock/watchlist.py`
- Modify: `src/us_stock/watchlist.py`
- Delete: `src/storage/runtime_store_v2.py`
- Modify: all callers under `src/`, `scripts/`, `windows_agent/`, and `tests/` returned by the verification command below
- Create: `tests/test_tenant_context.py`

- [ ] **Step 1: Add tenant validation tests**

Create `tests/test_tenant_context.py`:

```python
import pytest

from src.core.tenant import SYSTEM_TENANT, TenantContext


def test_tenant_context_rejects_empty_user_id():
    with pytest.raises(ValueError, match="user_id is required"):
        TenantContext("")


def test_system_tenant_is_explicit():
    assert SYSTEM_TENANT.user_id == "system"
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_tenant_context.py 2>&1 | head -c 4000
```

Expected: import failure because `src/core/tenant.py` does not exist.

- [ ] **Step 3: Add the immutable tenant value object**

Create `src/core/tenant.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TenantContext:
    user_id: str

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise ValueError("user_id is required")


SYSTEM_TENANT = TenantContext("system")
```

- [ ] **Step 4: Bind `RuntimeStore` to one tenant**

Change its constructor to:

```python
class RuntimeStore:
    def __init__(self, engine, tenant: TenantContext) -> None:
        self.engine = engine
        self.tenant = tenant

    @property
    def user_id(self) -> str:
        return self.tenant.user_id
```

For every user-owned method, remove the `user_id` parameter and replace query/write uses with `self.user_id`. For example:

```python
def get_decision_run(self, decision_run_id: str) -> dict | None:
    with self.engine.begin() as conn:
        row = conn.execute(
            select(DecisionRunRow)
            .where(DecisionRunRow.decision_run_id == decision_run_id)
            .where(DecisionRunRow.user_id == self.user_id)
        ).first()
```

Apply this transformation to all user-owned method groups: execution plans, decision runs/snapshots, target positions, execution orders, risk events, account snapshots, preferences, Alpha tickets/fills/positions/snapshots/reconciliation/watchlists/API attempts, and dashboard summaries/events.

- [ ] **Step 5: Move global operations into `SystemRuntimeStore`**

Create `src/storage/system_runtime_store.py` with this boundary:

```python
from sqlalchemy import or_, select

from src.storage.models import ExecutionOrderRow


class SystemRuntimeStore:
    def __init__(self, engine) -> None:
        self.engine = engine

    def resolve_execution_order_owner(self, order_id: str) -> tuple[str, str, str] | None:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(
                    ExecutionOrderRow.user_id,
                    ExecutionOrderRow.execution_order_id,
                    ExecutionOrderRow.run_context_id,
                ).where(
                    or_(
                        ExecutionOrderRow.execution_order_id == order_id,
                        ExecutionOrderRow.broker_order_id == order_id,
                    )
                )
            ).one_or_none()
        return tuple(row) if row else None
```

Move these methods from `RuntimeStore` without leaving wrappers:

- `set_kill_switch`
- `get_kill_switch`
- `list_kill_switch_events`
- `insert_kill_switch_event`
- broker owner resolution and callback ingress coordination

Keep scheduler locking in `PaperLedgerStore` because its table and transaction already live there.

- [ ] **Step 6: Bind Paper and watchlist Stores at construction**

Change `PaperLedgerStore` to:

```python
class PaperLedgerStore:
    def __init__(self, session: Session, tenant: TenantContext):
        self._session = session
        self._tenant = tenant

    @property
    def user_id(self) -> str:
        return self._tenant.user_id
```

Remove `user_id` from every user-owned paper-ledger method and use `self.user_id`. Keep `acquire_job_lock` global and remove its unused `user_id` parameter.

Change both watchlist constructors to accept `TenantContext`, and use `tenant.user_id` internally.

- [ ] **Step 7: Provide authenticated Store dependencies**

In `src/api/dependencies.py` add:

```python
def get_tenant_context(user_id: str = Depends(get_current_user_id)) -> TenantContext:
    return TenantContext(user_id)


def get_user_runtime_store(
    tenant: TenantContext = Depends(get_tenant_context),
) -> RuntimeStore:
    return RuntimeStore(get_runtime_engine(), tenant)
```

`src/storage/dependencies.py` must expose only the canonical engine accessor and `SystemRuntimeStore` accessor. Remove any unauthenticated singleton `RuntimeStore` construction.

- [ ] **Step 8: Migrate all callers in one pass**

Use these transformations consistently:

```python
# Before
store = RuntimeStore(engine)
store.list_decision_runs(user_id=user_id)

# After
store = RuntimeStore(engine, TenantContext(user_id))
store.list_decision_runs()
```

For scheduler, CLI, backfill, and system-only use:

```python
store = RuntimeStore(engine, SYSTEM_TENANT)
```

For Paper Ledger:

```python
ledger = PaperLedgerStore(session, TenantContext(user_id))
account = ledger.get_or_create_account(market, account_kind)
```

- [ ] **Step 9: Delete parallel and fallback paths**

Delete `src/storage/runtime_store_v2.py`. Remove duplicate `SYSTEM_USER_ID` declarations and remove ORM-side `default=SYSTEM_USER_ID` from all user-owned columns. Columns remain `nullable=False`; callers must supply the bound tenant.

Run:

```bash
rg -n 'runtime_store_v2|user_id or "system"|user_id: str = SYSTEM_USER_ID|default=SYSTEM_USER_ID' src tests scripts windows_agent 2>&1 | head -c 12000
```

Expected: no output, except explicit `SYSTEM_TENANT` imports/usages in CLI, scheduler, and backfill paths.

- [ ] **Step 10: Run Store and caller tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_tenant_context.py tests/test_runtime_store_pg.py tests/test_paper_ledger_store.py tests/a_stock tests/us_stock tests/test_alpha_runtime_store.py tests/test_dashboard_api.py 2>&1 | head -c 12000
```

Expected: all tests pass.

- [ ] **Step 11: Commit**

```bash
git add src tests scripts windows_agent
git commit -m "refactor: bind user stores to tenant context"
```

### Task 5: Fix the Alpha Watchlist Composite Primary Key

**Files:**
- Modify: `src/storage/models.py:264-274`
- Create: `alembic/versions/20260620_000016_harden_user_isolation.py`
- Modify: `tests/test_alpha_runtime_store.py:82-95`

- [ ] **Step 1: Add a failing same-symbol two-user test**

Replace the Alpha watchlist test with:

```python
def test_alpha_watchlist_allows_same_symbol_for_different_users(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    alice = RuntimeStore(engine, TenantContext("alice"))
    bob = RuntimeStore(engine, TenantContext("bob"))

    alice.add_alpha_watchlist_item(symbol="AAPLx", underlying_symbol="AAPL", priority=1)
    bob.add_alpha_watchlist_item(symbol="AAPLx", underlying_symbol="AAPL", priority=2)

    assert alice.list_alpha_watchlist_items()[0]["priority"] == 1
    assert bob.list_alpha_watchlist_items()[0]["priority"] == 2

    alice.remove_alpha_watchlist_item("AAPLx")
    assert alice.list_alpha_watchlist_items() == []
    assert bob.list_alpha_watchlist_items()[0]["symbol"] == "AAPLx"
```

- [ ] **Step 2: Run the test and verify the primary-key collision**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_alpha_runtime_store.py::test_alpha_watchlist_allows_same_symbol_for_different_users 2>&1 | head -c 4000
```

Expected: `IntegrityError` because `symbol` is the current global primary key.

- [ ] **Step 3: Change the ORM model to a composite primary key**

Use:

```python
class AlphaWatchlistItemRow(Base):
    __tablename__ = "alpha_watchlist_items"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    underlying_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

Remove `uq_alpha_watchlist_user_symbol`; the composite primary key is authoritative.

- [ ] **Step 4: Add the migration without foreign keys**

Create revision `20260620_000016` with `down_revision = "20260620_000015"`. In `upgrade()`, use Alembic batch mode so SQLite migration tests and PostgreSQL both support the primary-key replacement:

```python
def upgrade() -> None:
    with op.batch_alter_table("alpha_watchlist_items", recreate="always") as batch_op:
        batch_op.drop_constraint("uq_alpha_watchlist_user_symbol", type_="unique")
        batch_op.drop_constraint("alpha_watchlist_items_pkey", type_="primary")
        batch_op.create_primary_key(
            "pk_alpha_watchlist_items",
            ["user_id", "symbol"],
        )
```

The migration must inspect constraint names before dropping because SQLite batch reflection may not preserve PostgreSQL names. It must not create any foreign key.

- [ ] **Step 5: Run Alpha and migration tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_alpha_runtime_store.py tests/test_alpha_routes.py 2>&1 | head -c 8000
/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head 2>&1 | head -c 8000
```

Expected: tests pass and Alembic upgrades to `20260620_000016`.

- [ ] **Step 6: Commit**

```bash
git add src/storage/models.py alembic/versions/20260620_000016_harden_user_isolation.py tests/test_alpha_runtime_store.py
git commit -m "fix: scope alpha watchlist primary key by user"
```

### Task 6: Derive Broker Event Ownership on the Server

**Files:**
- Modify: `src/storage/models.py:28-36`
- Modify: `alembic/versions/20260620_000016_harden_user_isolation.py`
- Modify: `src/storage/system_runtime_store.py`
- Modify: `src/storage/runtime_store.py:450-586`
- Modify: `src/api/routes_broker_events.py`
- Replace: `tests/test_broker_event_api.py`
- Create: `tests/test_broker_event_isolation.py`

- [ ] **Step 1: Add callback ownership tests**

Create tests that insert one execution order for Alice and one for Bob, then submit a signed callback whose payload falsely contains Bob's ID but whose `order_id` belongs to Alice:

```python
def test_broker_event_derives_user_from_order(pg_engine):
    alice = RuntimeStore(pg_engine, TenantContext("alice"))
    bob = RuntimeStore(pg_engine, TenantContext("bob"))
    system = SystemRuntimeStore(pg_engine)
    order_id = insert_test_order(alice, run_context_id="run-alice")

    system.record_broker_event(
        event_id="event-1",
        order_id=order_id,
        event_type="FILLED",
        payload={"user_id": "bob", "pnl_delta": 12.5},
    )

    assert alice.list_broker_events()[0]["event_id"] == "event-1"
    assert bob.list_broker_events() == []
```

Also add:

```python
def test_broker_event_rejects_unknown_order(system_store):
    with pytest.raises(LookupError, match="execution order not found"):
        system_store.record_broker_event("event-1", "missing", "FILLED", {})
```

- [ ] **Step 2: Run the tests and verify failure**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_broker_event_isolation.py 2>&1 | head -c 6000
```

Expected: failure because `broker_events` has no `user_id` and global listing exposes the event to both users.

- [ ] **Step 3: Add tenant ownership to broker events**

Change the model to:

```python
class BrokerEventRow(Base):
    __tablename__ = "broker_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_context_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

Extend migration `000016` to add `user_id` temporarily nullable, backfill it by joining `execution_orders` on either internal or broker order ID, fail if unresolved rows remain, then make it non-null and create `ix_broker_events_user_id`. Do not create a foreign key.

- [ ] **Step 4: Implement authoritative owner resolution and write**

Add to `SystemRuntimeStore`:

```python
def record_broker_event(
    self,
    event_id: str,
    order_id: str,
    event_type: str,
    payload: dict,
) -> str:
    clean_payload = {key: value for key, value in payload.items() if key != "user_id"}
    with self.engine.begin() as conn:
        owner = conn.execute(
            select(
                ExecutionOrderRow.user_id,
                ExecutionOrderRow.execution_order_id,
                ExecutionOrderRow.run_context_id,
            ).where(
                or_(
                    ExecutionOrderRow.execution_order_id == order_id,
                    ExecutionOrderRow.broker_order_id == order_id,
                )
            )
        ).one_or_none()
        if owner is None:
            raise LookupError(f"execution order not found: {order_id}")
        user_id, execution_order_id, run_context_id = owner
        conn.execute(
            BrokerEventRow.__table__.insert().values(
                event_id=event_id,
                user_id=user_id,
                order_id=execution_order_id,
                run_context_id=run_context_id,
                event_type=event_type,
                payload_json=json.dumps(clean_payload, ensure_ascii=True, sort_keys=True),
            )
        )
    return user_id
```

Owner lookup and event insertion deliberately share one transaction. `resolve_execution_order_owner` remains available for read-only diagnostics, but the write path must not call it in a separate transaction.

Change `RuntimeStore.list_broker_events` to always filter `BrokerEventRow.user_id == self.user_id`. Remove the old global insert/list methods.

- [ ] **Step 5: Make the HMAC route reject unresolved orders**

Inject `SystemRuntimeStore` and map `LookupError` to 404:

```python
try:
    user_id = store.record_broker_event(
        event_id=str(event["event_id"]),
        order_id=str(event["order_id"]),
        event_type=str(event["event_type"]),
        payload=event,
    )
except LookupError as exc:
    raise HTTPException(status_code=404, detail=str(exc)) from exc
return {"received": True, "event_type": event["event_type"], "user_id": user_id}
```

The returned `user_id` is acceptable for this trusted HMAC integration endpoint; if external disclosure is undesirable, omit it and assert ownership through storage tests instead.

- [ ] **Step 6: Run broker tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_broker_event_api.py tests/test_broker_event_isolation.py tests/test_runtime_store_pg.py 2>&1 | head -c 10000
```

Expected: all tests pass; unknown orders return 404; payload `user_id` cannot affect ownership.

- [ ] **Step 7: Commit**

```bash
git add src/storage/models.py src/storage/runtime_store.py src/storage/system_runtime_store.py src/api/routes_broker_events.py alembic/versions/20260620_000016_harden_user_isolation.py tests/test_broker_event_api.py tests/test_broker_event_isolation.py
git commit -m "fix: derive broker event ownership from orders"
```

### Task 7: Isolate Dashboard Events, Reconciliation, and PnL

**Files:**
- Modify: `src/storage/runtime_store.py:633-715`
- Modify: `src/api/routes_dashboard.py:625-852`
- Modify: `tests/test_dashboard_api.py`
- Modify: `tests/test_runtime_store_pg.py`
- Create: `tests/test_user_isolation.py`

- [ ] **Step 1: Add two-user aggregate tests**

Create `tests/test_user_isolation.py` with one FILLED broker event per user and assert:

```python
def test_dashboard_aggregates_are_tenant_scoped(seed_two_user_broker_events):
    alice, bob = seed_two_user_broker_events

    assert alice.sum_daily_pnl() == 10.0
    assert bob.sum_daily_pnl() == -4.0
    assert [row["event_id"] for row in alice.list_broker_events()] == ["alice-event"]
    assert [row["event_id"] for row in bob.list_broker_events()] == ["bob-event"]
    assert alice.get_reconciliation_status()["broker_event_count"] == 1
    assert bob.get_reconciliation_status()["broker_event_count"] == 1
```

Add an authenticated Dashboard API test asserting Alice's JSON does not contain `bob-event`, Bob's symbol, or Bob's PnL.

- [ ] **Step 2: Run tests and verify cross-user aggregation failure**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_user_isolation.py tests/test_dashboard_api.py 2>&1 | head -c 8000
```

Expected: daily PnL and reconciliation counts include both users.

- [ ] **Step 3: Filter every broker-derived aggregate by the bound tenant**

Use:

```python
broker_events_stmt = (
    select(func.count())
    .select_from(BrokerEventRow)
    .where(BrokerEventRow.user_id == self.user_id)
)
```

Change `sum_daily_pnl` to have no `user_id` argument and include:

```python
.where(
    BrokerEventRow.user_id == self.user_id,
    BrokerEventRow.event_type == "FILLED",
    BrokerEventRow.created_at >= day_start,
    BrokerEventRow.created_at < day_end,
)
```

Change `_list_recent_events(store, limit)` to use the already tenant-bound Store. Kill Switch events remain global, but broker events are tenant-scoped.

- [ ] **Step 4: Run aggregate and dashboard tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_user_isolation.py tests/test_dashboard_api.py tests/test_runtime_store_pg.py tests/test_reconciliation.py 2>&1 | head -c 10000
```

Expected: all tests pass and neither user's response contains the other's event, position, or PnL.

- [ ] **Step 5: Commit**

```bash
git add src/storage/runtime_store.py src/api/routes_dashboard.py tests/test_user_isolation.py tests/test_dashboard_api.py tests/test_runtime_store_pg.py
git commit -m "fix: isolate broker-derived dashboard aggregates"
```

### Task 8: Enforce Paper Ledger Ownership Without Foreign Keys

**Files:**
- Modify: `src/paper_ledger/store.py:26-243`
- Modify: `src/paper_ledger/backfill.py`
- Modify: `src/scheduler/daily_scheduler.py`
- Modify: `tests/test_paper_ledger_store.py`
- Modify: `tests/test_daily_scheduler.py`

- [ ] **Step 1: Add cross-user update and relation tests**

Append to `tests/test_paper_ledger_store.py`:

```python
def test_run_status_update_cannot_cross_tenants(session):
    alice = PaperLedgerStore(session, TenantContext("alice"))
    bob = PaperLedgerStore(session, TenantContext("bob"))
    account = alice.get_or_create_account("a", "manual")
    run = alice.create_run(account.account_id, "a", date.today(), "manual", {}, [])

    with pytest.raises(LookupError, match="paper run not found"):
        bob.update_run_status(run.run_id, "success")


def test_fill_requires_run_and_account_owned_by_tenant(session):
    alice = PaperLedgerStore(session, TenantContext("alice"))
    bob = PaperLedgerStore(session, TenantContext("bob"))
    account = alice.get_or_create_account("a", "manual")
    run = alice.create_run(account.account_id, "a", date.today(), "manual", {}, [])

    with pytest.raises(LookupError, match="paper run not found"):
        bob.create_fill(run.run_id, account.account_id, "600519.SH", "BUY", 100, 10.0)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_paper_ledger_store.py 2>&1 | head -c 6000
```

Expected: Bob can update Alice's run by globally unique `run_id`, or method signatures still permit arbitrary user IDs.

- [ ] **Step 3: Scope updates and validate ownership in the transaction**

Implement:

```python
def update_run_status(self, run_id: str, status: str, error_message: str | None = None) -> None:
    run = self._session.execute(
        select(PaperRunRow).where(
            PaperRunRow.run_id == run_id,
            PaperRunRow.user_id == self.user_id,
        )
    ).scalar_one_or_none()
    if run is None:
        raise LookupError(f"paper run not found: {run_id}")
    run.status = status
    run.error_message = error_message
    self._session.commit()
```

Before creating fills, NAV rows, positions, or runs, query the referenced account/run with `user_id == self.user_id`; raise `LookupError` on mismatch. These checks replace foreign keys for tenant consistency and must occur in the same SQLAlchemy session/transaction as the write.

- [ ] **Step 4: Update scheduler and backfill callers**

Construct `PaperLedgerStore(session, SYSTEM_TENANT)` for scheduler/backfill. Remove `SCHEDULER_USER_ID` and direct string constants; `SYSTEM_TENANT` is the only system identity.

- [ ] **Step 5: Run ledger and scheduler tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_paper_ledger_store.py tests/test_daily_scheduler.py tests/test_paper_ledger_backfill.py 2>&1 | head -c 10000
```

Expected: all tests pass; cross-user references fail before insertion.

- [ ] **Step 6: Commit**

```bash
git add src/paper_ledger src/scheduler/daily_scheduler.py tests/test_paper_ledger_store.py tests/test_daily_scheduler.py
git commit -m "fix: enforce paper ledger tenant ownership"
```

### Task 9: Audit Global Operations and Kill Switch Attribution

**Files:**
- Modify: `src/storage/models.py:136-142`
- Modify: `alembic/versions/20260620_000016_harden_user_isolation.py`
- Modify: `src/storage/system_runtime_store.py`
- Modify: `src/api/routes_kill_switch.py`
- Modify: `tests/test_kill_switch_api.py`

- [ ] **Step 1: Add actor-attribution tests**

Add:

```python
def test_kill_switch_event_records_authenticated_actor(authenticated_admin_client, system_store):
    response = authenticated_admin_client.post(
        "/api/v1/kill-switch/activate",
        json={"reason": "manual halt"},
    )
    assert response.status_code == 200
    event = system_store.list_kill_switch_events(limit=1)[0]
    assert event["actor_user_id"] == "test-user"
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_kill_switch_api.py 2>&1 | head -c 4000
```

Expected: event data has no actor.

- [ ] **Step 3: Add nullable actor attribution without a foreign key**

Add to `KillSwitchEventRow`:

```python
actor_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
```

Extend migration `000016` with the nullable column and index only. Existing events remain null; do not invent an actor during backfill.

Change the system Store write signature:

```python
def insert_kill_switch_event(self, actor_user_id: str, active: bool, reason: str | None = None) -> None:
```

Pass `get_current_user_id` from activate/deactivate routes. CLI and scheduler callers pass `SYSTEM_TENANT.user_id` explicitly.

- [ ] **Step 4: Run Kill Switch tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_kill_switch_api.py tests/test_redis_kill_switch_cache.py 2>&1 | head -c 8000
```

Expected: all tests pass and every newly written event has an explicit actor.

- [ ] **Step 5: Commit**

```bash
git add src/storage/models.py src/storage/system_runtime_store.py src/api/routes_kill_switch.py alembic/versions/20260620_000016_harden_user_isolation.py tests/test_kill_switch_api.py
git commit -m "feat: attribute global kill switch actions"
```

### Task 10: Document and Verify the Single Isolation Path

**Files:**
- Create: `docs/runbooks/user-isolation.md`
- Modify: `AGENTS.md`
- Modify: tests discovered by the full suite only when failures are caused by the new canonical interfaces

- [ ] **Step 1: Write the operational contract**

Create `docs/runbooks/user-isolation.md` with these exact rules:

```markdown
# User Isolation

## Authentication

- Login uses the signed `access_token` HttpOnly Cookie.
- Token expiry and Cookie Max-Age are both `AUTH_SESSION_HOURS=168` (7 days).
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
```

Add the same concise invariants under the architecture section of `AGENTS.md`.

- [ ] **Step 2: Verify no forbidden fallback or parallel implementation remains**

Run:

```bash
rg -n 'runtime_store_v2|user_id or "system"|username == "tengjiaozhai"|default=SYSTEM_USER_ID|PROTECTED_PREFIXES' src tests scripts windows_agent 2>&1 | head -c 12000
```

Expected: no output.

Verify no foreign key was introduced:

```bash
rg -n 'ForeignKey|create_foreign_key|sa\.ForeignKey' src/storage src/paper_ledger alembic/versions/20260620_000016_harden_user_isolation.py 2>&1 | head -c 12000
```

Expected: no new matches in revision `000016`; pre-existing unrelated matches, if any, must be reported rather than changed.

- [ ] **Step 3: Run migration verification on a fresh SQLite database**

Run:

```bash
DATABASE_URL=sqlite:////tmp/a-share-hub-isolation.db /opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head 2>&1 | head -c 12000
DATABASE_URL=sqlite:////tmp/a-share-hub-isolation.db /opt/anaconda3/envs/py311/bin/python3 -m alembic current 2>&1 | head -c 4000
```

Expected: current revision is `20260620_000016`.

- [ ] **Step 4: Run focused security tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q tests/test_auth_security.py tests/test_auth_routes.py tests/test_route_authentication.py tests/test_broker_event_isolation.py tests/test_user_isolation.py tests/test_alpha_runtime_store.py tests/test_paper_ledger_store.py tests/test_kill_switch_api.py 2>&1 | head -c 16000
```

Expected: all tests pass.

- [ ] **Step 5: Run full quality gates**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest -q 2>&1 | head -c 20000
/opt/anaconda3/envs/py311/bin/python3 -m ruff check src tests 2>&1 | head -c 12000
/opt/anaconda3/envs/py311/bin/python3 -m mypy src 2>&1 | head -c 12000
```

Expected: all tests pass, Ruff reports no errors, and MyPy reports no errors.

- [ ] **Step 6: Review the final schema invariants**

Using SQLAlchemy inspection in a test or one-off read-only command, verify:

- `broker_events.user_id` is non-null and indexed.
- `alpha_watchlist_items` primary key is `(user_id, symbol)`.
- `kill_switch_events.actor_user_id` exists and is indexed.
- No foreign keys were added.
- All user-owned ORM `user_id` columns are non-null and have no Python/server default.

- [ ] **Step 7: Commit documentation and final test repairs**

```bash
git add AGENTS.md docs/runbooks/user-isolation.md tests
git commit -m "docs: define user isolation operating contract"
```

## Self-Review Results

- Spec coverage: seven-day existing token architecture, no foreign keys, Broker ownership, Alpha composite key, tenant-bound Stores, system fail-fast behavior, explicit admin grants, router dependencies, Kill Switch attribution, stale tests, documentation, and full verification are all assigned to tasks.
- Single-path check: the plan deletes `runtime_store_v2.py`, removes optional/default user IDs, and does not add compatibility wrappers.
- Type consistency: all user stores use `TenantContext`; global operations use `SystemRuntimeStore`; `SYSTEM_TENANT` is the only system identity value object.
- Migration consistency: all schema changes are contained in revision `20260620_000016`, based on current head `20260620_000015`, with no foreign keys.
- Known constraint: migration backfill must fail if any existing broker event cannot be matched to an execution order. This is intentional fail-fast behavior; operators must clean orphan rows before rerunning migration.
