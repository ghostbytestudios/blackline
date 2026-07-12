"""Encrypted database layer.

The database is **never written to disk in plaintext**. While unlocked it lives in an
in-memory SQLite connection; it is persisted only as an AES-256-GCM-encrypted blob
(`blackline.db.enc`) produced via `sqlite3.Connection.serialize()` (stdlib, Python 3.11+).

Lifecycle:
  locked  -> no connection, no sessions possible
  unlock  -> decrypt blob (or create fresh) into memory; sessions available
  commit  -> re-serialize + encrypt + atomically write the blob
  lock    -> dispose engine, drop the in-memory DB and key

Because the decryption key comes from the passphrase, a wrong passphrase simply fails
to decrypt the blob (authenticated encryption) — there is no separate password check.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings
from .security import crypto

# AAD bound to the encrypted DB blob. This value is an opaque, versioned tag and must
# stay stable forever — changing the bytes makes any existing vault undecryptable.
# (Legacy codename, intentionally left unchanged through the Blackline rename.)
_DB_AAD = b"vaultcfo-db-v1"


class Base(DeclarativeBase):
    pass


class DatabaseLocked(Exception):
    """Raised when a DB session is requested while the database is locked."""


class SecureDatabase:
    def __init__(self) -> None:
        self._raw: sqlite3.Connection | None = None
        self._engine = None
        self._sessionmaker: sessionmaker | None = None
        self._key: bytes | None = None
        self._io_lock = threading.Lock()
        self._suspend_persist = False

    @property
    def is_open(self) -> bool:
        return self._sessionmaker is not None

    def open(self, key: bytes) -> bool:
        """Open the DB with `key`. Decrypts an existing blob or creates a fresh DB.

        Returns True if the database was freshly created. Raises crypto.DecryptionError
        if an existing blob cannot be decrypted (i.e. wrong passphrase).
        """
        settings = get_settings()
        settings.ensure_dirs()

        raw = sqlite3.connect(":memory:", check_same_thread=False)
        raw.execute("PRAGMA foreign_keys=ON")

        fresh = True
        enc_path = settings.db_enc_path
        if enc_path.exists():
            blob = enc_path.read_bytes()
            nonce, ciphertext = blob[: crypto.NONCE_LEN], blob[crypto.NONCE_LEN :]
            data = crypto.decrypt(key, nonce, ciphertext, aad=_DB_AAD)  # may raise
            raw.deserialize(data)
            fresh = False

        self._raw = raw
        self._key = key
        self._engine = create_engine(
            "sqlite://",
            creator=lambda: raw,
            poolclass=StaticPool,
            future=True,
        )
        self._sessionmaker = sessionmaker(
            bind=self._engine, autoflush=False, expire_on_commit=False, future=True
        )
        # Persist after every committed write so the encrypted blob stays current.
        event.listen(self._sessionmaker, "after_commit", self._on_commit)

        from . import models  # noqa: F401  (register tables on Base.metadata)
        from .migrate import upgrade_to_head

        if fresh:
            # Fresh vault: create the full current schema directly. Existing vaults
            # evolve exclusively through migration scripts (see app/migrate.py).
            Base.metadata.create_all(self._engine)
        upgrade_to_head(self._engine, fresh=fresh)
        self.persist()  # materialize the stamp/migrations (and fresh vaults) immediately
        return fresh

    def _on_commit(self, _session: Session) -> None:
        if not self._suspend_persist:
            self.persist()

    @contextmanager
    def paused_persistence(self) -> Iterator[None]:
        """Temporarily suppress auto-persist (used during an atomic re-key)."""
        self._suspend_persist = True
        try:
            yield
        finally:
            self._suspend_persist = False

    def rekey(self, new_key: bytes) -> None:
        """Switch the at-rest encryption key and atomically rewrite the blob under it.

        Crash-safety: the salt is unchanged, so this single atomic write is the only
        on-disk mutation. Before it lands, the old blob (old key) remains fully valid;
        after it lands, the new blob (new key) is fully valid. There is no inconsistent
        intermediate on disk.
        """
        self._key = new_key
        self.persist()

    def persist(self) -> None:
        """Serialize, encrypt, and atomically write the DB blob."""
        if self._raw is None or self._key is None:
            return
        with self._io_lock:
            data = self._raw.serialize()
            nonce, ciphertext = crypto.encrypt(self._key, data, aad=_DB_AAD)
            enc_path = get_settings().db_enc_path
            tmp = enc_path.with_suffix(".tmp")
            tmp.write_bytes(nonce + ciphertext)
            os.replace(tmp, enc_path)  # atomic on the same filesystem

    def rotate_backup(self) -> Path | None:
        """Copy the current encrypted blob into the backup dir and prune old copies.

        The blob is AES-GCM ciphertext, so a copy is exactly as safe at rest as the
        original. The atomic write in `persist` protects against crashes mid-write;
        rotation protects against disk faults and a corrupted blob being the only copy.
        Returns the backup path, or None if there is nothing to back up / disabled.
        """
        settings = get_settings()
        src = settings.db_enc_path
        if not src.exists() or settings.backup_count <= 0:
            return None
        backup_dir = settings.backup_dir
        backup_dir.mkdir(parents=True, exist_ok=True)
        # Microseconds keep names unique even for rotations within the same second
        # (e.g. the pre-restore snapshot taken right after a fresh backup).
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        dest = backup_dir / f"{src.name}.{stamp}.bak"
        with self._io_lock:  # don't copy while persist() is mid-replace
            shutil.copy2(src, dest)
        backups = sorted(backup_dir.glob(f"{src.name}.*.bak"))
        for old in backups[: -settings.backup_count]:
            old.unlink(missing_ok=True)
        return dest

    def restore_from(self, path: Path, key: bytes) -> None:
        """Replace the live DB with a backup blob and reopen it.

        The backup is read and decrypt-verified in memory *before* anything on disk
        changes, so a wrong-key backup (e.g. made before a passphrase change) is
        rejected with no side effects. The current blob is snapshotted into the
        backup rotation first, making the restore itself reversible.
        """
        blob = path.read_bytes()
        nonce, ciphertext = blob[: crypto.NONCE_LEN], blob[crypto.NONCE_LEN :]
        crypto.decrypt(key, nonce, ciphertext, aad=_DB_AAD)  # raises DecryptionError
        self.rotate_backup()  # pre-restore snapshot (may prune `path` — blob is in memory)
        self.close()
        enc_path = get_settings().db_enc_path
        tmp = enc_path.with_suffix(".tmp")
        tmp.write_bytes(blob)
        os.replace(tmp, enc_path)
        self.open(key)  # migrations bring an older backup schema up to head

    def close(self) -> None:
        """Drop the in-memory DB and zeroize references. Committed data is already persisted."""
        with self._io_lock:
            if self._engine is not None:
                self._engine.dispose()  # StaticPool closes the underlying connection
            self._raw = None
            self._engine = None
            self._sessionmaker = None
            self._key = None

    def session(self) -> Session:
        if self._sessionmaker is None:
            raise DatabaseLocked("database is locked; unlock first")
        return self._sessionmaker()


# Process-wide singleton.
secure_db = SecureDatabase()


def get_db() -> Iterator[Session]:
    """FastAPI dependency. Read endpoints never commit (no persist); writes commit (persist)."""
    db = secure_db.session()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def read_scope() -> Iterator[Session]:
    """Read-only session that never commits (avoids needless re-encryption on reads)."""
    db = secure_db.session()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commits on success (triggering persist), rolls back on error."""
    db = secure_db.session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
