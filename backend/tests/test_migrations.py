"""Alembic bootstrapping: fresh vaults are stamped, pre-Alembic vaults upgraded."""

from __future__ import annotations

import os

from alembic.migration import MigrationContext
from sqlalchemy import text

from app.db import SecureDatabase
from app.migrate import BASELINE_REVISION

KEY = os.urandom(32)


def _current_revision(sdb: SecureDatabase) -> str | None:
    with sdb._engine.connect() as conn:  # noqa: SLF001 (test reaches into internals)
        return MigrationContext.configure(conn).get_current_revision()


def test_fresh_vault_stamped_at_head(tmp_data_dir):
    sdb = SecureDatabase()
    assert sdb.open(KEY) is True
    assert _current_revision(sdb) is not None
    sdb.close()


def test_pre_alembic_vault_bootstrapped_to_baseline_then_head(tmp_data_dir):
    # Simulate a vault created before Alembic existed: full schema, no version table.
    sdb = SecureDatabase()
    sdb.open(KEY)
    with sdb.session() as s:
        s.execute(text("DROP TABLE alembic_version"))
        s.commit()
    sdb.close()

    sdb2 = SecureDatabase()
    assert sdb2.open(KEY) is False  # existing vault
    rev = _current_revision(sdb2)
    assert rev is not None
    assert rev >= BASELINE_REVISION  # stamped at baseline, then upgraded to head
    sdb2.close()


def test_version_stamp_survives_reopen(tmp_data_dir):
    sdb = SecureDatabase()
    sdb.open(KEY)
    with sdb.session() as s:
        head = s.execute(text("SELECT version_num FROM alembic_version")).scalar()
    sdb.close()

    sdb2 = SecureDatabase()
    sdb2.open(KEY)
    with sdb2.session() as s:
        assert s.execute(text("SELECT version_num FROM alembic_version")).scalar() == head
    sdb2.close()
