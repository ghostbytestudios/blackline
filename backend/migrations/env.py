"""Alembic environment.

Blackline's database is an encrypted in-memory SQLite connection that only exists
while the vault is unlocked, so migrations run *in-process* at unlock time (see
`app/migrate.py`), never via the alembic CLI against a URL.
"""

from alembic import context

from app.db import Base
from app import models  # noqa: F401  (register tables on Base.metadata)

target_metadata = Base.metadata

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError(
        "Blackline migrations run in-process against the decrypted in-memory database. "
        "Apply them by unlocking the vault in the app; the alembic CLI has no URL to use."
    )

context.configure(
    connection=connection,
    target_metadata=target_metadata,
    render_as_batch=True,  # SQLite can't ALTER in place; batch mode recreates tables
)

with context.begin_transaction():
    context.run_migrations()
