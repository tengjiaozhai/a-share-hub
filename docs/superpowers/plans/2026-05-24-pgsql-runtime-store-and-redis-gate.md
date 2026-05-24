# PostgreSQL 运行时存储与 Redis 负载门控实现计划

> **对于智能代理工作者：** 必需的子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 来逐任务实施此计划。步骤使用复选框（`- [ ]`）语法进行跟踪。

**目标：** 将控制平面运行时存储从之前的 SQLite 计划迁移到 PostgreSQL，使用现有的 `.env` 数据库设置，规范化环境契约，并将 Redis 仅作为可选的负载门控缓存层添加，它永远不会成为真实数据源。

**架构：** PostgreSQL 成为执行计划、券商事件、紧急停止开关状态和对账元数据的单一权威持久化层。Redis 仅在显式 `REDIS_ENABLED` 门控后引入，并且仅用于临时缓存、速率限制或幂等性加速（在测量的服务器负载阈值超过后）；即使启用了 Redis，PostgreSQL 仍然是权威数据源。

**技术栈：** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, psycopg 3, Redis 5.x, Pydantic v2, pydantic-settings, pytest, httpx

---

## 范围与约束

- 此计划替代了之前修复计划中基于 SQLite 的 `RuntimeStore` 方向。
- `.env` 中的 `DATABASE_URL` 是唯一权威的运行时存储连接字符串。
- Redis 默认未启用。它作为可选阶段添加，不能持有权威的执行计划、券商事件或紧急停止开关真实数据。
- `.env` 当前混合了应用、数据库、Redis、LLM 和 SSH 凭据，并且重用了像 `USER_NAME` 和 `PASSWORD` 这样有歧义的名称。此计划在将其连接到更多代码之前规范化该契约。
- 在 PostgreSQL 路径通过且测量负载证明其必要之前，不要开始 Redis 工作。

## 观察到的 AWS 基线

- SSH 验证的主机：`13.214.201.113`
- CPU：`2 vCPU`
- 内存：`3.7 GiB 总计`，约 `3.0 GiB 可用`，`0 swap`
- 磁盘：根卷 `8.0 GiB 总计`，约 `4.4 GiB 空闲`
- PostgreSQL：已安装并 `active`
- PostgreSQL 数据占用：约 `47 MiB`
- Redis：未安装且未运行

## 容量决策

- PostgreSQL 应成为此主机上的默认运行时存储后端。它已安装、活动且当前占用较小。
- Redis 只能作为受约束的可选缓存适配。在此主机类别上，它不能被视为必需的基线依赖项。
- 如果稍后在此主机上启用 Redis，初始限制必须保守：`REDIS_MAXMEMORY_MB=128`，仅缓存角色，默认无持久化。
- 如果影子流量留下的可用内存少于 `1.5 GiB` 或空闲磁盘少于 `3 GiB`，则不得启用 Redis。

## 文件结构锁定

- 修改：`.env` — 停止使用有歧义的键名，使 PostgreSQL/Redis 意图明确。
- 创建：`.env.example` — 不含机密的清理模板。
- 修改：`.gitignore` — 确保 `.env` 不再被跟踪。
- 修改：`pyproject.toml` — 添加 PostgreSQL 驱动并保持 Redis 可选。
- 修改：`README.md` — 记录 PostgreSQL 优先的运行时存储和 Redis 负载门控。
- 修改：`src/core/config.py` — 解析规范化的数据库、Redis 和服务器设置。
- 创建：`src/storage/db.py` — 使用 `DATABASE_URL` 的 SQLAlchemy 引擎/会话工厂。
- 创建：`src/storage/models.py` — PostgreSQL 中的运行时存储表。
- 创建：`src/storage/runtime_store.py` — 支持 PostgreSQL 的运行时存储。
- 创建：`src/storage/redis_cache.py` — 可选的 Redis 缓存后端。
- 修改：`src/api/routes_execution_plans.py` — 读写支持 PostgreSQL 的运行时存储。
- 修改：`src/api/routes_broker_events.py` — 在 PostgreSQL 中持久化券商事件。
- 修改：`src/api/routes_kill_switch.py` — 在 PostgreSQL 中持久化紧急停止开关状态，并可选地在 Redis 中缓存读取。
- 修改：`src/main.py` — 初始化支持数据库的应用和运行时存储依赖项。
- 修改：`windows_agent/pull_execution_plans.py` — 使用支持数据库的 API，并仅将缓存的紧急停止开关作为提示。
- 创建：`alembic.ini`
- 创建：`alembic/env.py`
- 创建：`alembic/versions/20260524_000001_runtime_store_pgsql.py`
- 创建：`tests/test_config_env.py`
- 创建：`tests/test_runtime_store_pg.py`
- 创建：`tests/test_kill_switch_pg.py`
- 创建：`tests/test_redis_cache.py`
- 创建：`tests/test_load_gate_policy.py`
- 创建：`docs/runbooks/infrastructure-load-gate.md`

## 从当前 `.env` 得出的假设

- `DATABASE_URL` 已经指向 PostgreSQL 并应保持权威。
- `REDIS_URL` 已存在但尚无代码使用它。
- 当前的 `.env` 对数据库/应用身份和 SSH 身份重用 `USER_NAME`，并且对不兼容的含义重用 `PASSWORD`。这些键在规范化的契约中必须不存在。
- 服务器容量现已通过 SSH 验证。Redis 启用仍必须依赖于在影子流量期间捕获的测量运行时指标，而不是偏好。

### 任务 1：围绕 PostgreSQL 和可选 Redis 规范化环境契约

**文件：**
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/.env`
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/.env.example`
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/.gitignore`
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/src/core/config.py`
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/tests/test_config_env.py`

- [ ] **步骤 1：编写失败的环境契约测试**

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/tests/test_config_env.py
from pathlib import Path

from src.core.config import Settings


def test_settings_reads_database_url_and_redis_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db-host:5432/hub")
    monkeypatch.setenv("REDIS_URL", "redis://redis-host:6379/0")
    monkeypatch.setenv("REDIS_ENABLED", "false")
    settings = Settings()
    assert settings.database_url == "postgresql+psycopg://user:pass@db-host:5432/hub"
    assert settings.redis_url == "redis://redis-host:6379/0"
    assert settings.redis_enabled is False


def test_settings_uses_explicit_ssh_keys_not_ambiguous_password(monkeypatch):
    monkeypatch.setenv("AWS_HOST", "10.0.0.1")
    monkeypatch.setenv("AWS_SSH_USER", "ec2-user")
    monkeypatch.setenv("AWS_SSH_KEY_PATH", "/tmp/key.pem")
    settings = Settings()
    assert settings.aws_host == "10.0.0.1"
    assert settings.aws_ssh_user == "ec2-user"
    assert settings.aws_ssh_key_path == Path("/tmp/key.pem")
```

- [ ] **步骤 2：运行测试以确认当前环境契约不完整**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_config_env.py -q
```

预期：
```text
FAILED tests/test_config_env.py::test_settings_reads_database_url_and_redis_url
FAILED tests/test_config_env.py::test_settings_uses_explicit_ssh_keys_not_ambiguous_password
```

- [ ] **步骤 3：实现规范化的环境契约**

```dotenv
# /Users/shenmingjie/workSpace/tranding/a-share-hub/.env.example
APP_ENV=development
APP_DEBUG=true
APP_LOG_LEVEL=INFO

DATABASE_URL=postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=5
DB_POOL_TIMEOUT_SECONDS=30
DB_ECHO=false

REDIS_ENABLED=false
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_ROLE=none
REDIS_MAXMEMORY_MB=128
REDIS_KILL_SWITCH_TTL_SECONDS=1
REDIS_READY_PLAN_TTL_SECONDS=5

LLM_PROVIDER=deepseek
LLM_API_KEY=change_me
LLM_MODEL=deepseek-chat

MARKET_DATA_PROVIDER=akshare
MAX_POSITION_RATIO=0.3
MAX_DAILY_LOSS_RATIO=0.05
STOP_LOSS_RATIO=0.08

NOTIFICATION_ENABLED=true
WECHAT_WORK_WEBHOOK=change_me

ENABLE_LIVE_TRADING=false
EXECUTION_MODE=shadow

AWS_HOST=127.0.0.1
AWS_SSH_USER=ec2-user
AWS_SSH_KEY_PATH=/path/to/key.pem
```

```gitignore
# /Users/shenmingjie/workSpace/tranding/a-share-hub/.gitignore
.env
.pytest_cache/
__pycache__/
*.pyc
```

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/src/core/config.py
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_debug: bool = True
    app_log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://app_user:change_me@127.0.0.1:5432/a_share_hub"
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout_seconds: int = 30
    db_echo: bool = False

    redis_enabled: bool = False
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_role: str = "none"
    redis_maxmemory_mb: int = 128
    redis_kill_switch_ttl_seconds: int = 1
    redis_ready_plan_ttl_seconds: int = 5

    api_token: str = "change_me"
    enable_live_trading: bool = False
    execution_mode: str = "shadow"

    aws_host: str = "127.0.0.1"
    aws_ssh_user: str = "ec2-user"
    aws_ssh_key_path: Path = Field(default=Path("/path/to/key.pem"))
```

```dotenv
# /Users/shenmingjie/workSpace/tranding/a-share-hub/.env
APP_ENV=development
APP_DEBUG=true
APP_LOG_LEVEL=INFO

DATABASE_URL=postgresql+psycopg://douya:douya@localhost:5432/douya
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=5
DB_POOL_TIMEOUT_SECONDS=30
DB_ECHO=false

REDIS_ENABLED=false
REDIS_URL=redis://localhost:6379/0
REDIS_ROLE=none
REDIS_MAXMEMORY_MB=128
REDIS_KILL_SWITCH_TTL_SECONDS=1
REDIS_READY_PLAN_TTL_SECONDS=5

LLM_PROVIDER=deepseek
LLM_API_KEY=change_me
LLM_MODEL=deepseek-chat

BROKER_API_KEY=change_me
BROKER_API_SECRET=change_me
BROKER_ACCOUNT_ID=change_me

MARKET_DATA_PROVIDER=akshare
MAX_POSITION_RATIO=0.3
MAX_DAILY_LOSS_RATIO=0.05
STOP_LOSS_RATIO=0.08

NOTIFICATION_ENABLED=true
WECHAT_WORK_WEBHOOK=change_me

ENABLE_LIVE_TRADING=false
EXECUTION_MODE=shadow

AWS_HOST=13.214.201.113
AWS_SSH_USER=ec2-user
AWS_SSH_KEY_PATH=/absolute/path/to/key.pem
```

- [ ] **步骤 4：运行任务 1 验收门控**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_config_env.py -q
```

预期：
```text
2 passed
```

验收标准：
- `DATABASE_URL` 是唯一的数据库连接权威。
- `REDIS_ENABLED=false` 默认设置。
- `REDIS_MAXMEMORY_MB=128` 定义为此主机类别的初始上限。
- SSH/服务器字段明确，不再重载 `PASSWORD` 或 `USER_NAME`。
- `.env.example` 存在且不包含真实机密。

- [ ] **步骤 5：提交任务 1**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add .env .env.example .gitignore src/core/config.py tests/test_config_env.py
git commit -m "chore: normalize postgres and redis environment contract"
```

### 任务 2：构建 PostgreSQL 运行时存储作为权威控制平面数据库

**文件：**
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/pyproject.toml`
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/src/storage/db.py`
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/src/storage/models.py`
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/src/storage/runtime_store.py`
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/tests/test_runtime_store_pg.py`

- [ ] **步骤 1：编写失败的 PostgreSQL 运行时存储测试**

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/tests/test_runtime_store_pg.py
from sqlalchemy import create_engine

from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_runtime_store_persists_ready_plan_in_relational_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    plan_id = store.insert_execution_plan(
        symbol="600519.SH",
        action="BUY",
        target_value=100000,
        reason="unit-test",
    )
    plans = store.list_ready_execution_plans()
    assert len(plans) == 1
    assert plans[0]["plan_id"] == plan_id


def test_runtime_store_persists_kill_switch_state(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    store.set_kill_switch(True)
    assert store.get_kill_switch() is True
```

- [ ] **步骤 2：运行测试以确认 PostgreSQL 存储尚不存在**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_runtime_store_pg.py -q
```

预期：
```text
E   ModuleNotFoundError: No module named 'src.storage'
```

- [ ] **步骤 3：实现权威的关系型运行时存储**

```toml
# /Users/shenmingjie/workSpace/tranding/a-share-hub/pyproject.toml
[project]
dependencies = [
    "akshare>=1.12.0",
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "requests>=2.31.0",
    "python-dotenv>=1.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "redis>=5.0.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.13.0",
    "psycopg[binary]>=3.2.0",
]
```

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/src/storage/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import Settings


def create_runtime_engine(settings: Settings):
    return create_engine(
        settings.database_url,
        future=True,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        echo=settings.db_echo,
    )


def create_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
```

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/src/storage/models.py
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ExecutionPlanRow(Base):
    __tablename__ = "execution_plans"

    plan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    target_value: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="READY")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class BrokerEventRow(Base):
    __tablename__ = "broker_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class KillSwitchRow(Base):
    __tablename__ = "kill_switch_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/src/storage/runtime_store.py
import json
import uuid

from sqlalchemy import select

from src.storage.models import BrokerEventRow, ExecutionPlanRow, KillSwitchRow


class RuntimeStore:
    def __init__(self, engine) -> None:
        self.engine = engine

    def insert_execution_plan(self, symbol: str, action: str, target_value: int, reason: str) -> str:
        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        with self.engine.begin() as conn:
            conn.execute(
                ExecutionPlanRow.__table__.insert().values(
                    plan_id=plan_id,
                    symbol=symbol,
                    action=action,
                    target_value=target_value,
                    reason=reason,
                    status="READY",
                )
            )
        return plan_id

    def list_ready_execution_plans(self) -> list[dict]:
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(ExecutionPlanRow).where(ExecutionPlanRow.status == "READY").order_by(ExecutionPlanRow.created_at)
            ).scalars()
            return [
                {
                    "plan_id": row.plan_id,
                    "symbol": row.symbol,
                    "action": row.action,
                    "target_value": row.target_value,
                    "reason": row.reason,
                }
                for row in rows
            ]

    def mark_plan_acknowledged(self, plan_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                ExecutionPlanRow.__table__.update().where(ExecutionPlanRow.plan_id == plan_id).values(status="ACKNOWLEDGED")
            )

    def insert_broker_event(self, event_id: str, order_id: str, event_type: str, payload: dict) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                BrokerEventRow.__table__.insert().values(
                    event_id=event_id,
                    order_id=order_id,
                    event_type=event_type,
                    payload_json=json.dumps(payload, ensure_ascii=True, sort_keys=True),
                )
            )

    def set_kill_switch(self, active: bool) -> None:
        with self.engine.begin() as conn:
            existing = conn.execute(select(KillSwitchRow).where(KillSwitchRow.id == 1)).scalar_one_or_none()
            if existing is None:
                conn.execute(KillSwitchRow.__table__.insert().values(id=1, active=active))
            else:
                conn.execute(KillSwitchRow.__table__.update().where(KillSwitchRow.id == 1).values(active=active))

    def get_kill_switch(self) -> bool:
        with self.engine.begin() as conn:
            row = conn.execute(select(KillSwitchRow).where(KillSwitchRow.id == 1)).scalar_one_or_none()
            return bool(row.active) if row is not None else False
```

- [ ] **步骤 4：运行任务 2 验收门控**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pip install -e .[dev]
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_runtime_store_pg.py -q
/opt/anaconda3/envs/py311/bin/python3 - <<'PY'
from src.core.config import Settings
from src.storage.db import create_runtime_engine

settings = Settings()
engine = create_runtime_engine(settings)
with engine.connect() as conn:
    conn.execute("select 1")
print("postgres runtime store reachable")
PY
```

预期：
```text
2 passed
postgres runtime store reachable
```

验收标准：
- PostgreSQL 是权威的运行时存储后端。
- 应用安装了可工作的 PostgreSQL 驱动。
- 代码可以从 `DATABASE_URL` 创建引擎并执行真实的连接检查。

- [ ] **步骤 5：提交任务 2**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add pyproject.toml src/storage/db.py src/storage/models.py src/storage/runtime_store.py tests/test_runtime_store_pg.py
git commit -m "feat: add postgresql runtime store"
```

### 任务 3：添加 Alembic 迁移并将 API 控制平面移至 PostgreSQL

**文件：**
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/alembic.ini`
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/alembic/env.py`
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/alembic/versions/20260524_000001_runtime_store_pgsql.py`
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/src/main.py`
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/src/api/routes_execution_plans.py`
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/src/api/routes_broker_events.py`
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/src/api/routes_kill_switch.py`
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/tests/test_kill_switch_pg.py`

- [ ] **步骤 1：编写失败的 API 持久化测试**

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/tests/test_kill_switch_pg.py
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.api.routes_kill_switch import activate_kill_switch, get_kill_switch_status
from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_activate_kill_switch_updates_store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    result = activate_kill_switch(store=store)
    assert result["activated"] is True
    assert store.get_kill_switch() is True


def test_ready_plans_endpoint_returns_persisted_plans(tmp_path):
    from src.api.routes_execution_plans import get_ready_plans

    engine = create_engine(f"sqlite:///{tmp_path}/runtime_store.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)
    store.insert_execution_plan(symbol="600519.SH", action="BUY", target_value=100000, reason="api-test")
    payload = get_ready_plans(store=store)
    assert payload[0]["symbol"] == "600519.SH"
```

- [ ] **步骤 2：运行测试以验证路由仍无后端存储**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_kill_switch_pg.py tests/test_execution_plan_api.py tests/test_broker_event_api.py -q
```

预期：
```text
FAILED tests/test_kill_switch_pg.py::test_activate_kill_switch_updates_store
FAILED tests/test_execution_plan_api.py::test_ready_plans_endpoint_returns_persisted_plans
```

- [ ] **步骤 3：实现迁移和 PostgreSQL 支持的 API 连接**

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/alembic/versions/20260524_000001_runtime_store_pgsql.py
from alembic import op
import sqlalchemy as sa


revision = "20260524_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_plans",
        sa.Column("plan_id", sa.String(length=64), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("target_value", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "broker_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("order_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "kill_switch_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("kill_switch_state")
    op.drop_table("broker_events")
    op.drop_table("execution_plans")
```

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/src/api/routes_execution_plans.py
from fastapi import APIRouter, Depends

from src.main import get_runtime_store

router = APIRouter(prefix="/api/v1")


def serialize_execution_plan(plan: dict) -> dict:
    return {
        "plan_id": plan["plan_id"],
        "symbol": plan["symbol"],
        "target_value": plan["target_value"],
        "action": plan["action"],
        "reason": plan["reason"],
    }


@router.get("/execution-plans/ready")
def get_ready_plans(store=Depends(get_runtime_store)) -> list[dict]:
    return [serialize_execution_plan(plan) for plan in store.list_ready_execution_plans()]


@router.post("/execution-plans/{plan_id}/ack")
def acknowledge_plan(plan_id: str, store=Depends(get_runtime_store)) -> dict:
    store.mark_plan_acknowledged(plan_id)
    return {"plan_id": plan_id, "acknowledged": True}
```

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/src/api/routes_broker_events.py
from fastapi import APIRouter, Depends

from src.main import get_runtime_store

router = APIRouter(prefix="/api/v1")


@router.post("/broker-events")
def receive_broker_event(event: dict, store=Depends(get_runtime_store)) -> dict:
    store.insert_broker_event(
        event_id=event["event_id"],
        order_id=event["order_id"],
        event_type=event["event_type"],
        payload=event,
    )
    return {"received": True, "event_type": event["event_type"]}
```

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/src/api/routes_kill_switch.py
from fastapi import APIRouter, Depends

from src.main import get_runtime_store

router = APIRouter(prefix="/api/v1")


@router.post("/kill-switch/activate")
def activate_kill_switch(store=Depends(get_runtime_store)) -> dict:
    store.set_kill_switch(True)
    return {"activated": True}


@router.post("/kill-switch/deactivate")
def deactivate_kill_switch(store=Depends(get_runtime_store)) -> dict:
    store.set_kill_switch(False)
    return {"deactivated": True}


@router.get("/kill-switch/status")
def get_kill_switch_status(store=Depends(get_runtime_store)) -> dict:
    return {"active": store.get_kill_switch()}
```

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/src/main.py
from functools import lru_cache

from fastapi import FastAPI

from src.api.routes_broker_events import router as broker_events_router
from src.api.routes_execution_plans import router as execution_plans_router
from src.api.routes_health import router as health_router
from src.api.routes_kill_switch import router as kill_switch_router
from src.core.config import Settings
from src.storage.db import create_runtime_engine
from src.storage.runtime_store import RuntimeStore


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@lru_cache(maxsize=1)
def get_runtime_store() -> RuntimeStore:
    settings = get_settings()
    engine = create_runtime_engine(settings)
    return RuntimeStore(engine)


def build_app() -> FastAPI:
    app = FastAPI(title="a-share-auto-trading-hub")
    app.include_router(health_router)
    app.include_router(execution_plans_router)
    app.include_router(broker_events_router)
    app.include_router(kill_switch_router)
    return app
```

- [ ] **步骤 4：运行任务 3 验收门控**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_kill_switch_pg.py tests/test_execution_plan_api.py tests/test_broker_event_api.py -q
/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head
/opt/anaconda3/envs/py311/bin/python3 - <<'PY'
from src.main import build_app
print(sorted(route.path for route in build_app().routes if route.path.startswith("/api/v1")))
PY
```

预期：
```text
all tests passed
['/api/v1/broker-events', '/api/v1/execution-plans/{plan_id}/ack', '/api/v1/execution-plans/ready', '/api/v1/kill-switch/activate', '/api/v1/kill-switch/deactivate', '/api/v1/kill-switch/status']
```

验收标准：
- API 路由通过 PostgreSQL 支持的运行时存储方法持久化。
- Alembic 可以在配置的 PostgreSQL 实例上创建模式。
- `build_app()` 暴露完整的控制平面。

- [ ] **步骤 5：提交任务 3**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add alembic.ini alembic src/main.py src/api/routes_execution_plans.py src/api/routes_broker_events.py src/api/routes_kill_switch.py tests/test_kill_switch_pg.py
git commit -m "feat: back control plane with postgresql runtime store"
```

### 任务 4：在显式负载门控后将 Redis 作为可选缓存层添加

**文件：**
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/src/storage/redis_cache.py`
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/src/api/routes_kill_switch.py`
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/src/api/routes_execution_plans.py`
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/tests/test_redis_cache.py`
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/tests/test_load_gate_policy.py`
- 创建：`/Users/shenmingjie/workSpace/tranding/a-share-hub/docs/runbooks/infrastructure-load-gate.md`

- [ ] **步骤 1：编写失败的 Redis 门控测试**

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/tests/test_redis_cache.py
from src.storage.redis_cache import should_use_redis_cache


def test_redis_cache_disabled_by_default():
    assert should_use_redis_cache(redis_enabled=False, redis_role="none") is False


def test_redis_cache_requires_explicit_runtime_role():
    assert should_use_redis_cache(redis_enabled=True, redis_role="cache") is True
```

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/tests/test_load_gate_policy.py
from src.storage.redis_cache import evaluate_redis_enablement


def test_redis_not_required_for_low_load_shadow_run():
    result = evaluate_redis_enablement(
        cpu_p95=35.0,
        memory_p95=48.0,
        api_latency_p95_ms=90.0,
        mem_available_mb=1200,
        disk_free_mb=3600,
        ready_plan_reads_per_second=2.0,
        broker_events_per_second=3.0,
        workers=1,
    )
    assert result["enable_redis"] is False
    assert "insufficient host reserve" in result["reasons"]


def test_redis_recommended_for_hot_read_or_multi_worker_load():
    result = evaluate_redis_enablement(
        cpu_p95=72.0,
        memory_p95=70.0,
        api_latency_p95_ms=260.0,
        mem_available_mb=1900,
        disk_free_mb=3600,
        ready_plan_reads_per_second=45.0,
        broker_events_per_second=25.0,
        workers=3,
    )
    assert result["enable_redis"] is True
    assert "multi-worker hot read load" in result["reasons"]
```

- [ ] **步骤 2：运行测试以验证 Redis 门控策略尚不存在**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_redis_cache.py tests/test_load_gate_policy.py -q
```

预期：
```text
E   ModuleNotFoundError: No module named 'src.storage.redis_cache'
```

- [ ] **步骤 3：将 Redis 实现为仅可选加速**

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/src/storage/redis_cache.py
import json

from redis import Redis


def should_use_redis_cache(redis_enabled: bool, redis_role: str) -> bool:
    return redis_enabled and redis_role == "cache"


def evaluate_redis_enablement(
    cpu_p95: float,
    memory_p95: float,
    api_latency_p95_ms: float,
    mem_available_mb: float,
    disk_free_mb: float,
    ready_plan_reads_per_second: float,
    broker_events_per_second: float,
    workers: int,
) -> dict:
    reasons: list[str] = []
    if mem_available_mb < 1536 or disk_free_mb < 3072:
        return {"enable_redis": False, "reasons": ["insufficient host reserve"]}
    if workers > 1 and ready_plan_reads_per_second >= 20.0:
        reasons.append("multi-worker hot read load")
    if api_latency_p95_ms >= 200.0 and ready_plan_reads_per_second >= 15.0:
        reasons.append("control-plane latency under repeated plan polling")
    if cpu_p95 >= 70.0 and memory_p95 >= 65.0:
        reasons.append("server saturation during shadow traffic")
    if broker_events_per_second >= 50.0:
        reasons.append("high broker event burst rate")
    return {"enable_redis": bool(reasons), "reasons": reasons}


class RedisCache:
    def __init__(self, redis_url: str) -> None:
        self.client = Redis.from_url(redis_url, decode_responses=True)

    def set_json(self, key: str, value: dict, ttl_seconds: int) -> None:
        self.client.set(name=key, value=json.dumps(value, ensure_ascii=True, sort_keys=True), ex=ttl_seconds)

    def get_json(self, key: str) -> dict | None:
        raw = self.client.get(key)
        return json.loads(raw) if raw else None
```

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/src/api/routes_kill_switch.py
from src.core.config import Settings
from src.storage.redis_cache import RedisCache, should_use_redis_cache


def get_kill_switch_status(store=Depends(get_runtime_store)) -> dict:
    settings = Settings()
    if should_use_redis_cache(settings.redis_enabled, settings.redis_role):
        cache = RedisCache(settings.redis_url)
        cached = cache.get_json("kill-switch-status")
        if cached is not None:
            return cached
    payload = {"active": store.get_kill_switch()}
    if should_use_redis_cache(settings.redis_enabled, settings.redis_role):
        RedisCache(settings.redis_url).set_json("kill-switch-status", payload, settings.redis_kill_switch_ttl_seconds)
    return payload
```

```markdown
# /Users/shenmingjie/workSpace/tranding/a-share-hub/docs/runbooks/infrastructure-load-gate.md
仅当以下所有条件都满足时才启用 Redis：

1. PostgreSQL 支持的影子流量已通过。
2. 已首先验证 `REDIS_ENABLED=false`。
3. 至少一个测量阈值在三个连续观察窗口内被超过：
   - `api_latency_p95_ms >= 200`
   - 当有多个工作者时 `ready_plan_reads_per_second >= 20`
   - `broker_events_per_second >= 50`
   - `cpu_p95 >= 70` 且 `memory_p95 >= 65`
4. 主机在 PostgreSQL 和应用进程后仍保留安全储备：
   - `MemAvailable >= 1536 MiB`
   - `disk free >= 3072 MiB`
   - `REDIS_MAXMEMORY_MB <= 128`
5. Redis 仅用于缓存、基于 TTL 的提示或幂等性加速。
6. PostgreSQL 仍然是执行计划、券商事件和紧急停止开关的真实数据源。
```

- [ ] **步骤 4：运行任务 4 验收门控**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_redis_cache.py tests/test_load_gate_policy.py -q
/opt/anaconda3/envs/py311/bin/python3 - <<'PY'
from src.storage.redis_cache import evaluate_redis_enablement
print(evaluate_redis_enablement(35.0, 48.0, 90.0, 1200, 3600, 2.0, 3.0, 1))
print(evaluate_redis_enablement(72.0, 70.0, 260.0, 1900, 3600, 45.0, 25.0, 3))
PY
```

预期：
```text
all tests passed
{'enable_redis': False, 'reasons': ['insufficient host reserve']}
{'enable_redis': True, 'reasons': ['multi-worker hot read load', 'control-plane latency under repeated plan polling', 'server saturation during shadow traffic']}
```

验收标准：
- Redis 默认保持禁用。
- Redis 启用取决于测量负载，而不是偏好。
- 如果内存或磁盘储备低于 SSH 验证的安全门控，则不能在此主机上启用 Redis。
- 即使启用了 Redis，PostgreSQL 仍然是真实数据源。

- [ ] **步骤 5：提交任务 4**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/storage/redis_cache.py src/api/routes_kill_switch.py src/api/routes_execution_plans.py tests/test_redis_cache.py tests/test_load_gate_policy.py docs/runbooks/infrastructure-load-gate.md
git commit -m "feat: add redis load gate as optional cache layer"
```

### 任务 5：更新运维文档和 PostgreSQL 优先部署的验收流程

**文件：**
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/README.md`
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/scripts/run_shadow_cycle.sh`
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/scripts/run_reconcile.sh`
- 修改：`/Users/shenmingjie/workSpace/tranding/a-share-hub/tests/test_e2e_shadow_cycle.py`

- [ ] **步骤 1：编写失败的文档和脚本测试**

```python
# /Users/shenmingjie/workSpace/tranding/a-share-hub/tests/test_e2e_shadow_cycle.py
from pathlib import Path


def test_shadow_cycle_mentions_postgresql_migration_and_not_sqlite():
    readme = Path("README.md").read_text()
    assert "DATABASE_URL" in readme
    assert "PostgreSQL" in readme
    assert "runtime_store_path" not in readme


def test_shadow_cycle_script_runs_migrations_before_runtime_commands():
    script = Path("scripts/run_shadow_cycle.sh").read_text()
    assert "alembic upgrade head" in script
    assert "python -m src.main run-decision" in script
```

- [ ] **步骤 2：运行测试以验证文档和脚本仍反映旧假设**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_e2e_shadow_cycle.py -q
```

预期：
```text
FAILED tests/test_e2e_shadow_cycle.py::test_shadow_cycle_mentions_postgresql_migration_and_not_sqlite
FAILED tests/test_e2e_shadow_cycle.py::test_shadow_cycle_script_runs_migrations_before_runtime_commands
```

- [ ] **步骤 3：实现 PostgreSQL 优先的操作员流程**

```bash
# /Users/shenmingjie/workSpace/tranding/a-share-hub/scripts/run_shadow_cycle.sh
#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/opt/anaconda3/envs/py311/bin/python3}"

cd "$REPO_ROOT"

"$PYTHON_BIN" -m alembic upgrade head
"$PYTHON_BIN" -m src.main sync-market --symbols 600519.SH --interval 5m --limit 32
"$PYTHON_BIN" -m src.main build-features --symbols 600519.SH --top-n 1
"$PYTHON_BIN" -m src.main run-decision --symbols 600519.SH --mock-llm
"$PYTHON_BIN" -m src.main plan-execution --symbols 600519.SH --nav 1000000
"$PYTHON_BIN" -m src.main shadow-execute --symbols 600519.SH --mock-broker
"$PYTHON_BIN" -m src.main reconcile --symbols 600519.SH
```

```bash
# /Users/shenmingjie/workSpace/tranding/a-share-hub/scripts/run_reconcile.sh
#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-/opt/anaconda3/envs/py311/bin/python3}"

cd "$REPO_ROOT"
"$PYTHON_BIN" -m alembic upgrade head
"$PYTHON_BIN" -m src.main reconcile --symbols 600519.SH
```

```markdown
# /Users/shenmingjie/workSpace/tranding/a-share-hub/README.md
## 运行时存储

运行时控制平面使用 PostgreSQL（通过 `DATABASE_URL`）。
Redis 是可选的，必须保持禁用直到负载门控运行手册另有说明。

## 引导

1. 从 `.env.example` 配置 `.env`。
2. 通过 `DATABASE_URL` 验证 PostgreSQL 连接。
3. 运行 `/opt/anaconda3/envs/py311/bin/python3 -m alembic upgrade head`。
4. 运行 `/opt/anaconda3/envs/py311/bin/python3 -m pytest -q`。
5. 运行 `bash scripts/run_shadow_cycle.sh`。
```

- [ ] **步骤 4：运行任务 5 验收门控**

运行：
```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_e2e_shadow_cycle.py -q
bash scripts/run_shadow_cycle.sh
bash scripts/run_reconcile.sh
```

预期：
```text
all tests passed
market snapshots synced for 1 symbols
decision input snapshots built for 1 symbols
decision runs created for 1 symbols
execution plans ready for approved targets
shadow execution completed with reconciled states
no unreconciled orders
```

验收标准：
- 运维文档说明 PostgreSQL 是必需的，Redis 是可选的。
- 影子脚本在运行时命令之前运行迁移。
- 没有剩余的运维路径假设 SQLite 运行时存储。

- [ ] **步骤 5：提交任务 5**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add README.md scripts/run_shadow_cycle.sh scripts/run_reconcile.sh tests/test_e2e_shadow_cycle.py
git commit -m "docs: switch runtime deployment to postgresql-first flow"
```

## 最终验收矩阵

- 任务 1 通过当 `.env` 和 `.env.example` 明确表达 PostgreSQL 和 Redis 角色而没有有歧义的凭据键时。
- 任务 2 通过当运行时存储通过 SQLAlchemy 持久化控制平面状态并可以使用 `DATABASE_URL` 连接时。
- 任务 3 通过当 Alembic 管理模式且所有控制平面路由读写 PostgreSQL 支持的状态时。
- 任务 4 通过当 Redis 证明是可选的、默认禁用且仅由测量的负载阈值启用时。
- 任务 5 通过当运维文档和脚本反映 PostgreSQL 优先的部署流程且影子周期仍然运行失败关闭时。

## 自审

- 规范覆盖：此计划使用实际的 `.env` 契约，将 PostgreSQL 作为权威数据库，仅在显式负载评估后添加 Redis。
- 占位符扫描：没有剩余的 `TODO`、`TBD`、"稍后实现"或"类似上述"占位符。
- 类型一致性：`DATABASE_URL`、`REDIS_URL`、`REDIS_ENABLED`、`redis_role`、`plan_id` 和 `event_id` 在配置、存储、API、测试和脚本中一致使用。