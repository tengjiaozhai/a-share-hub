import sqlalchemy as sa
from alembic import op


revision = "20260620_000013"
down_revision = "20260619_000012"
branch_labels = None
depends_on = None


SYSTEM_USER_ID = "system"


def upgrade() -> None:
    op.add_column(
        "a_share_watchlist",
        sa.Column(
            "user_id",
            sa.String(length=64),
            nullable=False,
            server_default=SYSTEM_USER_ID,
        ),
    )
    op.execute("UPDATE a_share_watchlist SET user_id = 'system' WHERE user_id IS NULL")
    op.drop_index("ix_a_share_watchlist_symbol", table_name="a_share_watchlist")
    op.create_index(
        "ix_a_share_watchlist_user_id", "a_share_watchlist", ["user_id"], unique=False
    )
    op.create_unique_constraint(
        "uq_a_share_watchlist_user_symbol",
        "a_share_watchlist",
        ["user_id", "symbol"],
    )

    op.add_column(
        "us_watchlist",
        sa.Column(
            "user_id",
            sa.String(length=64),
            nullable=False,
            server_default=SYSTEM_USER_ID,
        ),
    )
    op.execute("UPDATE us_watchlist SET user_id = 'system' WHERE user_id IS NULL")
    op.drop_index("ix_us_watchlist_symbol", table_name="us_watchlist")
    op.create_index(
        "ix_us_watchlist_user_id", "us_watchlist", ["user_id"], unique=False
    )
    op.create_unique_constraint(
        "uq_us_watchlist_user_symbol",
        "us_watchlist",
        ["user_id", "symbol"],
    )

    op.add_column(
        "alpha_watchlist_items",
        sa.Column(
            "user_id",
            sa.String(length=64),
            nullable=False,
            server_default=SYSTEM_USER_ID,
        ),
    )
    op.execute("UPDATE alpha_watchlist_items SET user_id = 'system' WHERE user_id IS NULL")
    op.create_index(
        "ix_alpha_watchlist_items_user_id",
        "alpha_watchlist_items",
        ["user_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_alpha_watchlist_user_symbol",
        "alpha_watchlist_items",
        ["user_id", "symbol"],
    )

    op.add_column(
        "user_preferences",
        sa.Column(
            "user_id",
            sa.String(length=64),
            nullable=False,
            server_default=SYSTEM_USER_ID,
        ),
    )
    op.execute("UPDATE user_preferences SET user_id = 'system' WHERE user_id IS NULL")
    op.drop_constraint("user_preferences_pkey", "user_preferences", type_="primary")
    op.create_primary_key(
        "user_preferences_pkey", "user_preferences", ["user_id", "key"]
    )


def downgrade() -> None:
    op.drop_constraint("user_preferences_pkey", "user_preferences", type_="primary")
    op.create_primary_key("user_preferences_pkey", "user_preferences", ["key"])
    op.drop_column("user_preferences", "user_id")

    op.drop_constraint(
        "uq_alpha_watchlist_user_symbol", "alpha_watchlist_items", type_="unique"
    )
    op.drop_index("ix_alpha_watchlist_items_user_id", table_name="alpha_watchlist_items")
    op.drop_column("alpha_watchlist_items", "user_id")

    op.drop_constraint(
        "uq_us_watchlist_user_symbol", "us_watchlist", type_="unique"
    )
    op.drop_index("ix_us_watchlist_user_id", table_name="us_watchlist")
    op.create_index("ix_us_watchlist_symbol", "us_watchlist", ["symbol"], unique=True)
    op.drop_column("us_watchlist", "user_id")

    op.drop_constraint(
        "uq_a_share_watchlist_user_symbol", "a_share_watchlist", type_="unique"
    )
    op.drop_index("ix_a_share_watchlist_user_id", table_name="a_share_watchlist")
    op.create_index(
        "ix_a_share_watchlist_symbol", "a_share_watchlist", ["symbol"], unique=True
    )
    op.drop_column("a_share_watchlist", "user_id")
