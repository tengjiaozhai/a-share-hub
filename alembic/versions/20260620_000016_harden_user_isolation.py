"""Composite primary key for alpha_watchlist_items and broker_events tenant column.

Revision ID: 20260620_000016
Revises: 20260620_000015
Create Date: 2026-06-20
"""
import sqlalchemy as sa
from alembic import op


revision = "20260620_000016"
down_revision = "20260620_000015"
branch_labels = None
depends_on = None


def _column_exists(inspector, table: str, column: str) -> bool:
    try:
        return any(c["name"] == column for c in inspector.get_columns(table))
    except Exception:
        return False


def _index_exists(inspector, table: str, index_name: str) -> bool:
    try:
        return any(idx["name"] == index_name for idx in inspector.get_indexes(table))
    except Exception:
        return False


def _constraint_exists(inspector, table: str, constraint_name: str) -> bool:
    try:
        for uq in inspector.get_unique_constraints(table):
            if uq.get("name") == constraint_name:
                return True
        for pk in inspector.get_pk_constraint(table).get("constrained_columns", []):
            if pk == constraint_name:
                return True
        return False
    except Exception:
        return False


def _pk_columns(inspector, table: str) -> list[str]:
    try:
        return list(inspector.get_pk_constraint(table).get("constrained_columns", []))
    except Exception:
        return []


def _column_has_default(inspector, table: str, column: str) -> bool:
    try:
        for c in inspector.get_columns(table):
            if c["name"] == column:
                return c.get("default") is not None
    except Exception:
        return False
    return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    _upgrade_alpha_watchlist(inspector)
    _upgrade_broker_events(inspector)


def _upgrade_alpha_watchlist(inspector) -> None:
    """alpha_watchlist_items: PK 改为 (user_id, symbol)。"""
    pk_cols = _pk_columns(inspector, "alpha_watchlist_items")

    if pk_cols != ["symbol"]:
        return

    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    existing_pk_name = inspector.get_pk_constraint("alpha_watchlist_items").get("name")

    # Drop server_default on user_id so the new PK column is a clean composite key.
    user_id_col = next(
        (c for c in inspector.get_columns("alpha_watchlist_items") if c["name"] == "user_id"),
        None,
    )
    has_server_default = user_id_col is not None and user_id_col.get("default") is not None

    if is_sqlite:
        with op.batch_alter_table("alpha_watchlist_items", recreate="always") as batch_op:
            if has_server_default:
                batch_op.alter_column("user_id", server_default=None)
            batch_op.drop_constraint("uq_alpha_watchlist_user_symbol", type_="unique")
            if existing_pk_name:
                batch_op.drop_constraint(existing_pk_name, type_="primary")
            batch_op.create_primary_key(
                "pk_alpha_watchlist_items",
                ["user_id", "symbol"],
            )
    else:
        op.execute("ALTER TABLE alpha_watchlist_items DROP CONSTRAINT IF EXISTS uq_alpha_watchlist_user_symbol")
        if existing_pk_name:
            op.execute(f"ALTER TABLE alpha_watchlist_items DROP CONSTRAINT IF EXISTS {existing_pk_name}")
        else:
            op.execute("ALTER TABLE alpha_watchlist_items DROP CONSTRAINT IF EXISTS alpha_watchlist_items_pkey")
        if has_server_default:
            op.alter_column("alpha_watchlist_items", "user_id", server_default=None)
        op.execute("ALTER TABLE alpha_watchlist_items ADD CONSTRAINT pk_alpha_watchlist_items PRIMARY KEY (user_id, symbol)")


def _upgrade_broker_events(inspector) -> None:
    """broker_events: 加 user_id + 索引（先 nullable，backfill 后非空）。"""
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if not _column_exists(inspector, "broker_events", "user_id"):
        op.add_column(
            "broker_events",
            sa.Column("user_id", sa.String(length=64), nullable=True),
        )

    op.execute(
        """
        UPDATE broker_events AS be
        SET user_id = eo.user_id
        FROM execution_orders AS eo
        WHERE be.order_id = eo.execution_order_id
          AND be.user_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE broker_events AS be
        SET user_id = eo.user_id
        FROM execution_orders AS eo
        WHERE be.order_id = eo.broker_order_id
          AND be.user_id IS NULL
        """
    )

    unresolved_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM broker_events WHERE user_id IS NULL")
    ).scalar_one()
    if unresolved_count > 0:
        raise RuntimeError(
            f"broker_events.user_id backfill failed: {unresolved_count} row(s) cannot be resolved from execution_orders. "
            "Resolve these rows manually before retrying the migration."
        )

    if is_sqlite:
        with op.batch_alter_table("broker_events") as batch_op:
            batch_op.alter_column("user_id", existing_type=sa.String(length=64), nullable=False)
    else:
        op.alter_column("broker_events", "user_id", existing_type=sa.String(length=64), nullable=False)

    if not _index_exists(inspector, "broker_events", "ix_broker_events_user_id"):
        op.create_index("ix_broker_events_user_id", "broker_events", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _index_exists(inspector, "broker_events", "ix_broker_events_user_id"):
        op.drop_index("ix_broker_events_user_id", table_name="broker_events")
    if _column_exists(inspector, "broker_events", "user_id"):
        with op.batch_alter_table("broker_events") as batch_op:
            batch_op.drop_column("user_id")

    pk_cols = _pk_columns(inspector, "alpha_watchlist_items")
    if "user_id" in pk_cols and "symbol" in pk_cols:
        bind = op.get_bind()
        is_sqlite = bind.dialect.name == "sqlite"
        existing_pk_name = inspector.get_pk_constraint("alpha_watchlist_items").get("name")
        if is_sqlite:
            with op.batch_alter_table("alpha_watchlist_items", recreate="always") as batch_op:
                if existing_pk_name:
                    batch_op.drop_constraint(existing_pk_name, type_="primary")
                batch_op.create_primary_key("alpha_watchlist_items_pkey", ["symbol"])
                batch_op.create_unique_constraint(
                    "uq_alpha_watchlist_user_symbol",
                    ["user_id", "symbol"],
                )
        else:
            if existing_pk_name:
                op.execute(f"ALTER TABLE alpha_watchlist_items DROP CONSTRAINT IF EXISTS {existing_pk_name}")
            else:
                op.execute("ALTER TABLE alpha_watchlist_items DROP CONSTRAINT IF EXISTS pk_alpha_watchlist_items")
            op.execute("ALTER TABLE alpha_watchlist_items ADD CONSTRAINT alpha_watchlist_items_pkey PRIMARY KEY (symbol)")
            op.execute(
                "ALTER TABLE alpha_watchlist_items ADD CONSTRAINT uq_alpha_watchlist_user_symbol UNIQUE (user_id, symbol)"
            )
