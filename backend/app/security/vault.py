"""Encrypted secret vault, backed by the `secrets` table.

Each secret is stored as (nonce, ciphertext). The AES-GCM `aad` is bound to the
secret's name so a ciphertext can't be silently swapped between slots.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Secret
from . import crypto

# Well-known secret slot names.
SIMPLEFIN_ACCESS_URL = "simplefin_access_url"
VERIFIER = "passphrase_verifier"
_VERIFIER_PLAINTEXT = b"ledgerlight-verifier-v1"


def put_secret(db: Session, key: bytes, name: str, plaintext: bytes) -> None:
    nonce, ct = crypto.encrypt(key, plaintext, aad=name.encode("utf-8"))
    existing = db.scalar(select(Secret).where(Secret.name == name))
    if existing is None:
        db.add(Secret(name=name, nonce=nonce, ciphertext=ct))
    else:
        existing.nonce = nonce
        existing.ciphertext = ct
    db.commit()


def get_secret(db: Session, key: bytes, name: str) -> bytes | None:
    row = db.scalar(select(Secret).where(Secret.name == name))
    if row is None:
        return None
    return crypto.decrypt(key, row.nonce, row.ciphertext, aad=name.encode("utf-8"))


def has_secret(db: Session, name: str) -> bool:
    return db.scalar(select(Secret.id).where(Secret.name == name)) is not None


def write_verifier(db: Session, key: bytes) -> None:
    """Store a known plaintext encrypted under the key; used to validate the passphrase."""
    put_secret(db, key, VERIFIER, _VERIFIER_PLAINTEXT)


def rekey_secrets(db: Session, old_key: bytes, new_key: bytes) -> int:
    """Re-encrypt every stored secret from old_key to new_key. Returns count re-encrypted.

    The caller is responsible for committing (and for ordering the DB-blob re-key).
    """
    count = 0
    for row in db.scalars(select(Secret)):
        plaintext = crypto.decrypt(old_key, row.nonce, row.ciphertext, aad=row.name.encode("utf-8"))
        row.nonce, row.ciphertext = crypto.encrypt(new_key, plaintext, aad=row.name.encode("utf-8"))
        count += 1
    return count


def verify_key(db: Session, key: bytes) -> bool:
    """Return True if `key` correctly decrypts the verifier (i.e. passphrase is right)."""
    try:
        return get_secret(db, key, VERIFIER) == _VERIFIER_PLAINTEXT
    except crypto.DecryptionError:
        return False
