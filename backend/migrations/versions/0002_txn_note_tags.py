"""Add user note + tags columns to transactions.

Defensive column-existence checks: vaults bootstrapped from a fresh install already
have these columns via create_all before being stamped, and the stamp-baseline path
must not fail when re-running against them (see app/migrate.py).
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _existing_columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    cols = _existing_columns("transactions")
    with op.batch_alter_table("transactions") as batch:
        if "note" not in cols:
            batch.add_column(sa.Column("note", sa.Text(), nullable=True))
        if "tags" not in cols:
            batch.add_column(
                sa.Column("tags", sa.Text(), nullable=False, server_default="")
            )


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch:
        batch.drop_column("tags")
        batch.drop_column("note")
