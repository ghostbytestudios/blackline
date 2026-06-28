"""In-memory application lock.

The app starts *locked*. Unlocking derives the encryption key from the passphrase and
opens the encrypted database (decrypting it). A wrong passphrase fails to decrypt the
DB blob, so it is rejected. First unlock creates a fresh encrypted DB and binds the
passphrase via a verifier secret.
"""

from __future__ import annotations

import threading

from ..config import get_settings
from ..db import secure_db, session_scope
from . import crypto, vault


class AppLock:
    def __init__(self) -> None:
        self._key: bytes | None = None
        self._mutex = threading.Lock()

    @property
    def is_initialized(self) -> bool:
        """True once a vault has been established (encrypted DB exists)."""
        return get_settings().db_enc_path.exists()

    @property
    def is_unlocked(self) -> bool:
        return self._key is not None and secure_db.is_open

    def _load_or_create_salt(self) -> bytes:
        settings = get_settings()
        settings.ensure_dirs()
        if settings.salt_path.exists():
            return settings.salt_path.read_bytes()
        salt = crypto.generate_salt()
        settings.salt_path.write_bytes(salt)
        return salt

    def unlock(self, passphrase: str) -> bool:
        """Unlock the vault. Returns True on success, False on wrong passphrase."""
        with self._mutex:
            salt = self._load_or_create_salt()
            key = crypto.derive_key(passphrase, salt)

            # Opening decrypts the DB; a wrong key fails authentication here.
            try:
                secure_db.open(key)
            except crypto.DecryptionError:
                return False

            with session_scope() as db:
                if vault.has_secret(db, vault.VERIFIER):
                    if not vault.verify_key(db, key):
                        secure_db.close()
                        return False
                else:
                    vault.write_verifier(db, key)

            self._key = key
            return True

    def lock(self) -> None:
        with self._mutex:
            secure_db.close()
            self._key = None

    def require_key(self) -> bytes:
        if self._key is None:
            raise LockedError("application is locked; unlock with your passphrase first")
        return self._key


class LockedError(Exception):
    """Raised when an operation needs the vault unlocked but it isn't."""


# Process-wide singleton.
app_lock = AppLock()
