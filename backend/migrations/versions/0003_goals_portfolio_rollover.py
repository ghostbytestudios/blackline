"""Goals table, portfolio snapshots table, and budget rollover flag.

Defensive existence checks for the same reason as 0002: freshly-created vaults
already have this schema from create_all before being stamped.
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "goals" not in tables:
        op.create_table(
            "goals",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("target_minor", sa.BigInteger(), nullable=False),
            sa.Column("target_date", sa.Date(), nullable=True),
            sa.Column("start_minor", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("account_ids", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "portfolio_snapshots" not in tables:
        op.create_table(
            "portfolio_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("as_of", sa.Date(), nullable=False, unique=True),
            sa.Column("total_value_minor", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("total_cost_minor", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )

    budget_cols = {c["name"] for c in inspector.get_columns("budgets")}
    if "rollover" not in budget_cols:
        with op.batch_alter_table("budgets") as batch:
            batch.add_column(
                sa.Column("rollover", sa.Boolean(), nullable=False, server_default="0")
            )


def downgrade() -> None:
    op.drop_table("portfolio_snapshots")
    op.drop_table("goals")
    with op.batch_alter_table("budgets") as batch:
        batch.drop_column("rollover")
