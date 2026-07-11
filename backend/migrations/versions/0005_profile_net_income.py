"""Optional manual take-home (net monthly) income on the profile.

Defensive existence check, same reason as 0002-0004: freshly-created vaults
already have this schema from create_all before being stamped.
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    cols = {c["name"] for c in inspector.get_columns("profile")}
    if "net_monthly_income_minor" not in cols:
        with op.batch_alter_table("profile") as batch:
            batch.add_column(sa.Column("net_monthly_income_minor", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("profile") as batch:
        batch.drop_column("net_monthly_income_minor")
