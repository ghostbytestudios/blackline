"""Backup listing/restore and portable vault export/import."""

from __future__ import annotations

import base64
import json

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import read_scope, secure_db, session_scope
from app.models import Account
from app.security import crypto
from app.security.lock import AppLock
from app.services import vault_admin

PASSPHRASE = "correct horse battery"


@pytest.fixture()
def lock(tmp_data_dir):
    lock = AppLock()
    assert lock.unlock(PASSPHRASE) is True
    yield lock
    lock.lock()


def add_account(name: str) -> None:
    with session_scope() as db:
        db.add(
            Account(
                external_id=f"va-{name}",
                name=name,
                account_type="depository",
                balance_minor=0,
            )
        )


def account_names() -> set[str]:
    with read_scope() as db:
        return {a.name for a in db.scalars(select(Account)).all()}


class TestListBackups:
    def test_no_backup_dir_is_empty(self, lock):
        assert vault_admin.list_backups() == []

    def test_lists_newest_first_and_ignores_foreign_files(self, lock):
        blob_name = get_settings().db_enc_path.name
        first = secure_db.rotate_backup()
        first.rename(first.with_name(f"{blob_name}.20200101-000000.bak"))
        second = secure_db.rotate_backup()
        second.rename(second.with_name(f"{blob_name}.20990101-000000.bak"))
        (get_settings().backup_dir / "notes.txt").write_text("not a backup")

        listed = vault_admin.list_backups()
        assert [b["name"] for b in listed] == [
            f"{blob_name}.20990101-000000.bak",
            f"{blob_name}.20200101-000000.bak",
        ]
        assert all(b["size_bytes"] > 0 for b in listed)

    def test_backup_path_rejects_traversal_and_unknown_names(self, lock):
        secure_db.rotate_backup()
        for bad in ("../vault.salt", "..\\vault.salt", "notes.txt", "nope.bak", ""):
            with pytest.raises(vault_admin.BackupNotFound):
                vault_admin.backup_path(bad)
        good = vault_admin.list_backups()[0]["name"]
        assert vault_admin.backup_path(good).name == good


class TestRestoreBackup:
    def test_restore_reverts_to_snapshot_state(self, lock):
        add_account("before")
        backup = secure_db.rotate_backup()
        add_account("after")
        assert account_names() == {"before", "after"}

        lock.restore_backup(backup)

        assert account_names() == {"before"}
        assert lock.is_unlocked
        # The pre-restore state was snapshotted, so the restore itself is undoable.
        names = [b["name"] for b in vault_admin.list_backups()]
        assert len(names) == 2

    def test_backup_from_old_passphrase_is_rejected_untouched(self, lock):
        add_account("keep")
        backup = secure_db.rotate_backup()
        assert lock.change_passphrase(PASSPHRASE, "a brand new passphrase") is True

        with pytest.raises(crypto.DecryptionError):
            lock.restore_backup(backup)

        # Nothing changed: still unlocked, data intact, no extra snapshot taken.
        assert lock.is_unlocked
        assert account_names() == {"keep"}
        assert len(vault_admin.list_backups()) == 1


class TestBundle:
    def test_export_parse_round_trip(self, lock):
        settings = get_settings()
        text = vault_admin.export_bundle()
        salt, blob = vault_admin.parse_bundle(text)
        assert salt == settings.salt_path.read_bytes()
        assert blob == settings.db_enc_path.read_bytes()

    def test_parse_rejects_garbage_and_wrong_format(self, lock):
        for bad in ("not json", "[]", json.dumps({"format": "other"})):
            with pytest.raises(vault_admin.BundleError):
                vault_admin.parse_bundle(bad)

    def test_parse_rejects_tampered_payloads(self, lock):
        doc = json.loads(vault_admin.export_bundle())
        for field, value in (
            ("version", 999),
            ("salt_b64", "%%%not-base64%%%"),
            ("salt_b64", base64.b64encode(b"short").decode()),
            ("blob_b64", base64.b64encode(b"tiny").decode()),
        ):
            broken = {**doc, field: value}
            with pytest.raises(vault_admin.BundleError):
                vault_admin.parse_bundle(json.dumps(broken))

    def test_parse_rejects_kdf_mismatch(self, lock):
        doc = json.loads(vault_admin.export_bundle())
        doc["kdf"]["time_cost"] = doc["kdf"]["time_cost"] + 1
        with pytest.raises(vault_admin.BundleError, match="key-derivation"):
            vault_admin.parse_bundle(json.dumps(doc))


class TestImportVault:
    def test_move_machines_round_trip(self, tmp_data_dir):
        # "Old machine": create a vault with data and export it.
        lock = AppLock()
        assert lock.unlock(PASSPHRASE) is True
        add_account("moved")
        bundle = vault_admin.export_bundle()
        lock.lock()

        # "New machine": wipe everything, then import the bundle.
        lock.reset_vault()
        assert lock.is_initialized is False
        salt, blob = vault_admin.parse_bundle(bundle)
        lock.import_vault(salt, blob)

        assert lock.is_initialized is True
        assert lock.is_unlocked is False
        assert lock.unlock("wrong passphrase!!") is False
        assert lock.unlock(PASSPHRASE) is True
        assert account_names() == {"moved"}
        lock.lock()

    def test_import_replaces_an_existing_vault(self, tmp_data_dir):
        lock = AppLock()
        assert lock.unlock(PASSPHRASE) is True
        add_account("original")
        bundle = vault_admin.export_bundle()
        lock.lock()

        # Diverge: new data after the export, then import the older bundle back.
        assert lock.unlock(PASSPHRASE) is True
        add_account("newer")
        salt, blob = vault_admin.parse_bundle(bundle)
        lock.import_vault(salt, blob)

        assert lock.is_unlocked is False  # import always leaves the app locked
        assert lock.unlock(PASSPHRASE) is True
        assert account_names() == {"original"}
        lock.lock()
