# AWS PG SSH Tunnel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep AWS PostgreSQL as the single source of truth while routing all real runtime database traffic through a managed local SSH tunnel with explicit readiness checks.

**Architecture:** The application continues to use `DATABASE_URL` as its only database authority, but in real runtime that URL points to a local loopback port such as `127.0.0.1:15432`. A systemd-managed SSH tunnel forwards that local port to the AWS host's `127.0.0.1:5432`, and all raw `psycopg` consumers are refactored to derive their DSN from the same canonical `DATABASE_URL`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, psycopg 3, PostgreSQL, systemd, bash, pytest

---

## File Structure

| File | Responsibility |
|---|---|
| `src/storage/connection_url.py` | Canonical `DATABASE_URL` parsing and psycopg DSN conversion |
| `src/storage/health.py` | Runtime DB probe used by readiness and ops scripts |
| `src/a_stock/routes.py` | Stop hand-building psycopg connection strings |
| `src/us_stock/routes.py` | Stop hand-building psycopg connection strings |
| `src/api/routes_health.py` | Keep liveness, add runtime DB readiness |
| `scripts/check_runtime_db.py` | CLI health probe for tunnel and runtime DB |
| `scripts/start_runtime_db_tunnel.sh` | Strict SSH local port forward bootstrap |
| `deploy/systemd/a-share-hub-runtime-db-tunnel.service` | Tunnel service template with restart policy |
| `scripts/init_a_share_watchlist.py` | Reuse canonical psycopg DSN helper |
| `scripts/init_us_watchlist.py` | Reuse canonical psycopg DSN helper |
| `.env.example` | Recommend loopback `DATABASE_URL` for real runtime |
| `README.md` | Runtime DB setup and verification updates |
| `docs/runbooks/aws-pg-ssh-tunnel.md` | Start, verify, restart, and troubleshoot tunnel setup |
| `tests/test_connection_url.py` | URL normalization and loopback guard tests |
| `tests/test_storage_health.py` | Probe behavior tests |
| `tests/test_health_api.py` | Readiness endpoint tests |
| `tests/a_stock/test_routes.py` | A-stock route still works after connection helper swap |
| `tests/us_stock/test_routes.py` | US-stock route still works after connection helper swap |

---

## Phase 1: Canonical Connection Authority

**Goal:** Make every PostgreSQL consumer derive its connection details from one helper instead of scattered string replacement logic.

**Files:**
- Create: `src/storage/connection_url.py`
- Modify: `src/a_stock/routes.py`
- Modify: `src/us_stock/routes.py`
- Modify: `scripts/init_a_share_watchlist.py`
- Modify: `scripts/init_us_watchlist.py`
- Test: `tests/test_connection_url.py`
- Modify: `tests/a_stock/test_routes.py`
- Modify: `tests/us_stock/test_routes.py`

- [ ] **Step 1: Write failing tests for URL normalization**

```python
from src.storage.connection_url import build_psycopg_dsn, extract_local_runtime_host_port


def test_build_psycopg_dsn_from_sqlalchemy_url():
    dsn = build_psycopg_dsn("postgresql+psycopg://user:pass@127.0.0.1:15432/douya")
    assert dsn == "postgresql://user:pass@127.0.0.1:15432/douya"


def test_extract_local_runtime_host_port_requires_loopback():
    host, port = extract_local_runtime_host_port("postgresql+psycopg://user:pass@127.0.0.1:15432/douya")
    assert host == "127.0.0.1"
    assert port == 15432
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_connection_url.py -q
```

Expected:

- FAIL because `src/storage/connection_url.py` does not exist yet

- [ ] **Step 3: Implement the minimal connection helper**

```python
from sqlalchemy.engine import make_url


def build_psycopg_dsn(database_url: str) -> str:
    url = make_url(database_url)
    drivername = url.drivername.split("+", 1)[0]
    return str(url.set(drivername=drivername))


def extract_local_runtime_host_port(database_url: str) -> tuple[str, int]:
    url = make_url(database_url)
    host = url.host or ""
    port = int(url.port or 5432)
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError(f"runtime DATABASE_URL must use loopback host, got: {host!r}")
    return host, port
```

- [ ] **Step 4: Refactor watchlist routes and init scripts to use the helper**

Target shape:

```python
from src.core.config import Settings
from src.storage.connection_url import build_psycopg_dsn


settings = Settings()
conn = psycopg.connect(
    build_psycopg_dsn(settings.database_url),
    row_factory=psycopg.rows.dict_row,
)
```

- [ ] **Step 5: Update route tests to keep behavior stable**

Add focused regression assertions around existing watchlist endpoints so the refactor stays behavior-only and does not change status codes or payload shape.

- [ ] **Step 6: Run the targeted test set**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest \
  tests/test_connection_url.py \
  tests/a_stock/test_routes.py \
  tests/us_stock/test_routes.py -q
```

Expected:

- PASS

**Acceptance Criteria:**

- No route or script manually performs `replace("postgresql+psycopg://", ...)`.
- `DATABASE_URL` remains the only connection authority.
- Existing A 股 / 美股 watchlist API behavior is unchanged.

---

## Phase 2: Runtime DB Probe And Readiness

**Goal:** Make database availability explicit and machine-checkable, without overloading the existing liveness endpoint.

**Files:**
- Create: `src/storage/health.py`
- Create: `scripts/check_runtime_db.py`
- Modify: `src/api/routes_health.py`
- Test: `tests/test_storage_health.py`
- Test: `tests/test_health_api.py`

- [ ] **Step 1: Write failing tests for the probe helper**

```python
from sqlalchemy import create_engine

from src.storage.health import probe_runtime_database


def test_probe_runtime_database_reports_ok_for_sqlite():
    engine = create_engine("sqlite:///:memory:", future=True)
    result = probe_runtime_database(engine)
    assert result["ok"] is True
    assert result["latency_ms"] >= 0
```

- [ ] **Step 2: Write failing API tests for readiness**

```python
from fastapi.testclient import TestClient

from src.main import build_app


def test_health_ready_returns_ok_when_probe_succeeds(monkeypatch):
    from src.api import routes_health

    monkeypatch.setattr(routes_health, "probe_runtime_database_from_settings", lambda: {"ok": True, "latency_ms": 3.2})
    client = TestClient(build_app())
    response = client.get("/health/ready")
    assert response.status_code == 200


def test_health_ready_returns_503_when_probe_fails(monkeypatch):
    from src.api import routes_health

    monkeypatch.setattr(routes_health, "probe_runtime_database_from_settings", lambda: {"ok": False, "error": "connect failed"})
    client = TestClient(build_app())
    response = client.get("/health/ready")
    assert response.status_code == 503
```

- [ ] **Step 3: Implement the minimal probe helper**

```python
from time import perf_counter

from sqlalchemy import text

from src.core.config import Settings
from src.storage.db import create_runtime_engine


def probe_runtime_database(engine) -> dict:
    started = perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = round((perf_counter() - started) * 1000, 2)
        return {"ok": True, "latency_ms": latency_ms}
    except Exception as exc:
        latency_ms = round((perf_counter() - started) * 1000, 2)
        return {"ok": False, "latency_ms": latency_ms, "error": str(exc)}


def probe_runtime_database_from_settings() -> dict:
    engine = create_runtime_engine(Settings())
    return probe_runtime_database(engine)
```

- [ ] **Step 4: Add `GET /health/ready` without changing `/health`**

Target shape:

```python
@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def health_ready():
    result = probe_runtime_database_from_settings()
    if not result["ok"]:
        raise HTTPException(status_code=503, detail=result)
    return {"status": "ok", **result}
```

- [ ] **Step 5: Add the ops probe script**

Target shape:

```python
from src.storage.health import probe_runtime_database_from_settings


def main() -> int:
    result = probe_runtime_database_from_settings()
    if result["ok"]:
        print(f"ok latency_ms={result['latency_ms']}")
        return 0
    print(f"error latency_ms={result['latency_ms']} detail={result['error']}")
    return 1
```

- [ ] **Step 6: Run the targeted test set**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest \
  tests/test_storage_health.py \
  tests/test_health_api.py -q
```

Expected:

- PASS

**Acceptance Criteria:**

- `/health` remains lightweight liveness.
- `/health/ready` fails fast when the runtime DB path is broken.
- `scripts/check_runtime_db.py` exits non-zero on connection failure.

---

## Phase 3: Managed SSH Tunnel

**Goal:** Move the SSH port forward into a restartable system service so the runtime DB path survives disconnects and machine restarts.

**Files:**
- Create: `scripts/start_runtime_db_tunnel.sh`
- Create: `deploy/systemd/a-share-hub-runtime-db-tunnel.service`
- Modify: `.env.example`
- Test: manual verification commands documented in runbook

- [ ] **Step 1: Write the strict tunnel launcher script**

Target shape:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

source "${REPO_ROOT}/.env"

LOCAL_PORT="$(
  /opt/anaconda3/envs/py311/bin/python3 - <<'PY'
from src.storage.connection_url import extract_local_runtime_host_port
from src.core.config import Settings
_, port = extract_local_runtime_host_port(Settings().database_url)
print(port)
PY
)"

exec ssh \
  -N \
  -i "${AWS_SSH_KEY_PATH}" \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=3 \
  -L "127.0.0.1:${LOCAL_PORT}:127.0.0.1:5432" \
  "${AWS_SSH_USER}@${AWS_HOST}"
```

- [ ] **Step 2: Add a systemd unit template**

Target shape:

```ini
[Unit]
Description=a-share-hub runtime DB tunnel
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/a-share-hub
ExecStart=/usr/bin/env bash /path/to/a-share-hub/scripts/start_runtime_db_tunnel.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 3: Update `.env.example` to show the runtime recommendation**

Required example:

```dotenv
DATABASE_URL=postgresql+psycopg://douya:change_me@127.0.0.1:15432/douya
AWS_HOST=13.214.201.113
AWS_SSH_USER=ec2-user
AWS_SSH_KEY_PATH=/path/to/key.pem
```

- [ ] **Step 4: Manually verify the tunnel launcher before systemd**

Run:

```bash
bash scripts/start_runtime_db_tunnel.sh
```

Expected:

- Local `127.0.0.1:<port>` starts listening
- The process stays attached in the foreground

- [ ] **Step 5: Verify runtime DB probe through the tunnel**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 scripts/check_runtime_db.py
```

Expected:

- Exit code `0`
- Output contains `ok latency_ms=...`

**Acceptance Criteria:**

- A versioned tunnel startup script exists in the repo.
- A versioned systemd unit template exists in the repo.
- Real runtime `DATABASE_URL` uses loopback and matches the tunnel local bind.

---

## Phase 4: Docs, Runbook, And Final Verification

**Goal:** Document the runtime contract clearly enough that operators use the tunnel path correctly and can diagnose failures quickly.

**Files:**
- Create: `docs/runbooks/aws-pg-ssh-tunnel.md`
- Modify: `README.md`
- Verify: `scripts/check_runtime_db.py`, `/health/ready`, targeted pytest

- [ ] **Step 1: Write the runbook**

The runbook must cover:

- required `.env` fields
- how to start the tunnel manually
- how to install and enable the systemd unit
- how to verify local bind and DB readiness
- what `503` on `/health/ready` means
- how to restart the tunnel and read logs

- [ ] **Step 2: Update README runtime storage guidance**

Replace generic PostgreSQL guidance with the recommended real-runtime contract:

- `DATABASE_URL` points to local loopback
- AWS DB is reached through SSH tunnel
- `scripts/check_runtime_db.py` is the first verification command

- [ ] **Step 3: Run regression tests**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest \
  tests/test_connection_url.py \
  tests/test_storage_health.py \
  tests/test_health_api.py \
  tests/a_stock/test_routes.py \
  tests/us_stock/test_routes.py -q
```

Expected:

- PASS

- [ ] **Step 4: Run final runtime checks**

Run:

```bash
/opt/anaconda3/envs/py311/bin/python3 scripts/check_runtime_db.py
curl -s http://127.0.0.1:8000/health/ready
```

Expected:

- tunnel up: probe succeeds and readiness returns `200`
- tunnel down: probe fails and readiness returns `503`

**Acceptance Criteria:**

- README and runbook describe one canonical runtime DB path.
- Operators can verify tunnel and DB readiness without reading source code.
- No hidden direct-to-AWS DB path remains in the app runtime code.

---

## Self-Review

### Spec coverage

- Loopback `DATABASE_URL`: covered in Phase 1 and Phase 3
- Single connection authority: covered in Phase 1
- Managed SSH tunnel: covered in Phase 3
- Readiness and fail-fast behavior: covered in Phase 2
- README and runbook updates: covered in Phase 4

### Placeholder scan

- No unresolved markers or dangling file references remain
- Each new file has a concrete purpose and verification step

### Type consistency

- Helper names are consistent: `build_psycopg_dsn`, `extract_local_runtime_host_port`, `probe_runtime_database`, `probe_runtime_database_from_settings`
