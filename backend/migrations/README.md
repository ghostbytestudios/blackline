# Schema migrations

Migrations run **in-process at unlock time** (`app/migrate.py`), not via the alembic
CLI — the database is an encrypted in-memory SQLite connection that only exists while
the vault is unlocked, so there is no URL for the CLI to connect to.

## Rules

- **Fresh vaults** get their schema from `Base.metadata.create_all()` and are stamped
  to head. Migration scripts never run on them.
- **Existing vaults** get every schema change through a migration script. If you add a
  table or column to `app/models.py`, you must also add a migration here, or existing
  vaults will break.
- SQLite can't `ALTER` most things in place; the env is configured with
  `render_as_batch=True`, so use `op.batch_alter_table(...)` for column changes.

## Adding a migration

1. Change `app/models.py`.
2. Create `versions/000N_short_name.py` by hand (copy the header pattern from
   `0001_baseline.py`, set `revision = "000N"` and `down_revision = "000N-1"`).
3. Write `upgrade()` with alembic `op.*` operations mirroring your model change.
4. Test: open a vault created before your change and confirm it unlocks and works.
