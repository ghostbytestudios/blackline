"""Baseline: the schema as it existed before Alembic was introduced.

Deliberately empty. Fresh vaults get their schema from `Base.metadata.create_all()`
and are stamped straight to head; pre-Alembic vaults (whose tables already exist)
are stamped here so future migrations have a starting point. See app/migrate.py.
"""

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
