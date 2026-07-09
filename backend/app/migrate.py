"""In-process Alembic runner.

The database is an in-memory SQLite connection that exists only while the vault is
unlocked, so migrations cannot run via the alembic CLI (there is no URL to point it
at). Instead `SecureDatabase.open()` calls `upgrade_to_head()` with the live engine
right after decrypting the blob.

Policy:
- **Fresh vault**: schema is created by `Base.metadata.create_all()` and stamped to
  head — migration scripts never run.
- **Existing vault**: schema changes ship exclusively as migration scripts under
  `backend/migrations/versions/`; `create_all` is not run (it would pre-create
  tables that a migration then fails to create).
- **Pre-Alembic vault** (no `alembic_version` table): stamped at the baseline
  revision, then upgraded to head.
"""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy.engine import Connection, Engine

from .config import BACKEND_ROOT

# Revision representing the schema as it existed before Alembic was introduced.
BASELINE_REVISION = "0001"


def _config(connection: Connection) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    cfg.attributes["connection"] = connection
    return cfg


def upgrade_to_head(engine: Engine, *, fresh: bool) -> None:
    with engine.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
        cfg = _config(conn)
        if fresh:
            command.stamp(cfg, "head")
        else:
            if current is None:
                command.stamp(cfg, BASELINE_REVISION)
            command.upgrade(cfg, "head")
        conn.commit()
