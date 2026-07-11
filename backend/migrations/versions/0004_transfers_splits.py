"""Transfer matching and transaction splitting columns on transactions.

Defensive existence checks for the same reason as 0002/0003: freshly-created
vaults already have this schema from create_all before being stamped.
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    txn_cols = {c["name"] for c in inspector.get_columns("transactions")}

    with op.batch_alter_table("transactions") as batch:
        if "transfer_peer_id" not in txn_cols:
            batch.add_column(sa.Column("transfer_peer_id", sa.Integer(), nullable=True))
        if "parent_id" not in txn_cols:
            batch.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
        if "is_split_parent" not in txn_cols:
            batch.add_column(
                sa.Column("is_split_parent", sa.Boolean(), nullable=False, server_default="0")
            )


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch:
        batch.drop_column("is_split_parent")
        batch.drop_column("parent_id")
        batch.drop_column("transfer_peer_id")
