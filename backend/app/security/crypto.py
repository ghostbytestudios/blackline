"""Cryptographic primitives.

- Key derivation: Argon2id (memory-hard) from the app passphrase + a per-install salt.
- Symmetric encryption: AES-256-GCM (authenticated encryption).

The derived key never touches disk. Only ciphertext + random nonce are persisted.
"""

from __future__ import annotations

import os

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import get_settings

KEY_LEN = 32  # AES-256
NONCE_LEN = 12
SALT_LEN = 16


class DecryptionError(Exception):
    """Raised when authentication/decryption fails (wrong key or tampering)."""


def generate_salt() -> bytes:
    return os.urandom(SALT_LEN)


def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 32-byte key from the passphrase using Argon2id."""
    s = get_settings()
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=s.argon2_time_cost,
        memory_cost=s.argon2_memory_kib,
        parallelism=s.argon2_parallelism,
        hash_len=KEY_LEN,
        type=Type.ID,
    )


def encrypt(key: bytes, plaintext: bytes, aad: bytes | None = None) -> tuple[bytes, bytes]:
    """Return (nonce, ciphertext) using AES-256-GCM."""
    nonce = os.urandom(NONCE_LEN)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return nonce, ct


def decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes | None = None) -> bytes:
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise DecryptionError("decryption failed (wrong passphrase or corrupted data)") from exc
