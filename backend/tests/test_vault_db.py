"""Encrypted DB lifecycle, secret vault, unlock throttle, and vault reset."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SecureDatabase
from app.models import Secret
from app.security import crypto, vault
from app.security.lock import AppLock, UnlockThrottle, app_lock


KEY = os.urandom(32)
WRONG_KEY = os.urandom(32)


class TestSecureDatabase:
    def test_fresh_open_creates_encrypted_blob(self, tmp_data_dir):
        sdb = SecureDatabase()
        assert sdb.open(KEY) is True
        assert get_settings().db_enc_path.exists()
        # The on-disk blob must not be a plaintext SQLite file.
        blob = get_settings().db_enc_path.read_bytes()
        assert not blob.startswith(b"SQLite format 3")
        sdb.close()

    def test_data_survives_close_and_reopen(self, tmp_data_dir):
        sdb = SecureDatabase()
        sdb.open(KEY)
        with sdb.session() as s:
            s.add(Secret(name="probe", nonce=b"x" * 12, ciphertext=b"y"))
            s.commit()
        sdb.close()

        sdb2 = SecureDatabase()
        assert sdb2.open(KEY) is False  # not fresh: decrypted the existing blob
        with sdb2.session() as s:
            assert s.scalar(select(Secret).where(Secret.name == "probe")) is not None
        sdb2.close()

    def test_wrong_key_rejected(self, tmp_data_dir):
        sdb = SecureDatabase()
        sdb.open(KEY)
        sdb.close()
        with pytest.raises(crypto.DecryptionError):
            SecureDatabase().open(WRONG_KEY)

    def test_rekey_old_key_invalid_new_key_valid(self, tmp_data_dir):
        sdb = SecureDatabase()
        sdb.open(KEY)
        sdb.rekey(WRONG_KEY)  # "wrong" key becomes the new right key
        sdb.close()
        with pytest.raises(crypto.DecryptionError):
            SecureDatabase().open(KEY)
        sdb2 = SecureDatabase()
        assert sdb2.open(WRONG_KEY) is False
        sdb2.close()

    def test_backup_rotation_prunes_to_configured_count(self, tmp_data_dir, monkeypatch):
        monkeypatch.setenv("BLACKLINE_BACKUP_COUNT", "2")
        get_settings.cache_clear()
        sdb = SecureDatabase()
        sdb.open(KEY)
        for i in range(3):
            dest = sdb.rotate_backup()
            assert dest is not None
            # Distinct names per rotation (timestamps are second-granular in reality).
            dest.rename(dest.with_suffix(f".{i}.bak"))
        backups = list(get_settings().backup_dir.glob("*.bak"))
        assert 1 <= len(backups) <= 2
        sdb.close()


class TestVaultSecrets:
    @pytest.fixture()
    def sdb(self, tmp_data_dir):
        sdb = SecureDatabase()
        sdb.open(KEY)
        yield sdb
        sdb.close()

    def test_secret_round_trip(self, sdb):
        with sdb.session() as s:
            vault.put_secret(s, KEY, "slot", b"hunter2")
            assert vault.get_secret(s, KEY, "slot") == b"hunter2"
            assert vault.has_secret(s, "slot") is True
            assert vault.get_secret(s, KEY, "missing") is None

    def test_secret_bound_to_slot_name(self, sdb):
        """AAD binding: ciphertext moved to another slot must not decrypt."""
        with sdb.session() as s:
            vault.put_secret(s, KEY, "slot-a", b"secret")
            row = s.scalar(select(Secret).where(Secret.name == "slot-a"))
            s.add(Secret(name="slot-b", nonce=row.nonce, ciphertext=row.ciphertext))
            s.commit()
            with pytest.raises(crypto.DecryptionError):
                vault.get_secret(s, KEY, "slot-b")

    def test_verifier_validates_key(self, sdb):
        with sdb.session() as s:
            vault.write_verifier(s, KEY)
            assert vault.verify_key(s, KEY) is True
            assert vault.verify_key(s, WRONG_KEY) is False

    def test_rekey_secrets(self, sdb):
        with sdb.session() as s:
            vault.put_secret(s, KEY, "slot", b"payload")
            count = vault.rekey_secrets(s, KEY, WRONG_KEY)
            s.commit()
            assert count == 1
            assert vault.get_secret(s, WRONG_KEY, "slot") == b"payload"


class TestUnlockThrottle:
    def test_free_attempts_then_escalating_delay(self):
        t = UnlockThrottle()
        for _ in range(3):
            t.record_failure()
            assert t.retry_after() == 0  # first three failures are free
        t.record_failure()
        assert 0 < t.retry_after() <= 2  # 2^1
        t.record_failure()
        assert 2 < t.retry_after() <= 4  # 2^2

    def test_delay_caps_at_max(self):
        t = UnlockThrottle()
        for _ in range(30):
            t.record_failure()
        assert t.retry_after() <= 60

    def test_reset_clears_state(self):
        t = UnlockThrottle()
        for _ in range(10):
            t.record_failure()
        t.reset()
        assert t.retry_after() == 0


class TestResetVault:
    def test_reset_deletes_blob_salt_and_backups(self, tmp_data_dir):
        settings = get_settings()
        settings.ensure_dirs()
        settings.db_enc_path.write_bytes(b"fake blob")
        settings.salt_path.write_bytes(b"fake salt")
        settings.backup_dir.mkdir(parents=True, exist_ok=True)
        (settings.backup_dir / "old.bak").write_bytes(b"fake backup")

        app_lock.reset_vault()

        assert not settings.db_enc_path.exists()
        assert not settings.salt_path.exists()
        assert not settings.backup_dir.exists()
        assert app_lock.is_initialized is False
        assert app_lock.is_unlocked is False


class TestAppLockLifecycle:
    def test_unlock_wrong_passphrase_then_correct(self, tmp_data_dir):
        lock = AppLock()
        assert lock.unlock("first passphrase!") is True  # creates the vault
        lock.lock()
        assert lock.unlock("wrong passphrase!") is False
        assert lock.is_unlocked is False
        assert lock.unlock("first passphrase!") is True
        lock.lock()

    def test_change_passphrase(self, tmp_data_dir):
        lock = AppLock()
        lock.unlock("original passphrase")
        assert lock.change_passphrase("wrong guess!", "new passphrase!!") is False
        assert lock.change_passphrase("original passphrase", "new passphrase!!") is True
        lock.lock()
        assert lock.unlock("original passphrase") is False
        assert lock.unlock("new passphrase!!") is True
        lock.lock()
