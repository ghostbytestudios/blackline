"""In-memory application lock.

The app starts *locked*. The user must unlock with their passphrase, which derives
the encryption key (held in memory only). Locking zeroizes the key reference.

First unlock establishes the passphrase (writes the salt + verifier). Subsequent
unlocks validate against the verifier.
"""

from __future__ import annotations

import threading

from ..config import get_settings
from ..db import session_scope
from . import crypto, vault


class AppLock:
    def __init__(self) -> None:
        self._key: bytes | None = None
        self._mutex = threading.Lock()

    @property
    def is_initialized(self) -> bool:
        """True once a passphrase has been established (salt file exists)."""
        return get_settings().salt_path.exists()

    @property
    def is_unlocked(self) -> bool:
        return self._key is not None

    def _load_or_create_salt(self) -> bytes:
        settings = get_settings()
        settings.ensure_dirs()
        if settings.salt_path.exists():
            return settings.salt_path.read_bytes()
        salt = crypto.generate_salt()
        # Write atomically-ish; restrictive perms best-effort (Windows ACLs vary).
        settings.salt_path.write_bytes(salt)
        return salt

    def unlock(self, passphrase: str) -> bool:
        """Unlock the vault. Returns True on success, False on wrong passphrase.

        On first use (no verifier yet) this establishes the passphrase.
        """
        with self._mutex:
            salt = self._load_or_create_salt()
            key = crypto.derive_key(passphrase, salt)
            with session_scope() as db:
                if vault.has_secret(db, vault.VERIFIER):
                    if not vault.verify_key(db, key):
                        return False
                else:
                    # First-time setup: bind this passphrase.
                    vault.write_verifier(db, key)
            self._key = key
            return True

    def lock(self) -> None:
        with self._mutex:
            self._key = None

    def require_key(self) -> bytes:
        if self._key is None:
            raise LockedError("application is locked; unlock with your passphrase first")
        return self._key


class LockedError(Exception):
    """Raised when an operation needs the vault unlocked but it isn't."""


# Process-wide singleton.
app_lock = AppLock()
