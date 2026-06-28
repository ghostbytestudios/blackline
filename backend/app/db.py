"""Encrypted database layer.

The database is **never written to disk in plaintext**. While unlocked it lives in an
in-memory SQLite connection; it is persisted only as an AES-256-GCM-encrypted blob
(`vaultcfo.db.enc`) produced via `sqlite3.Connection.serialize()` (stdlib, Python 3.11+).

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
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings
from .security import crypto

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

        Base.metadata.create_all(self._engine)
        if fresh:
            self.persist()  # materialize the encrypted file immediately
        return fresh

    def _on_commit(self, _session: Session) -> None:
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
