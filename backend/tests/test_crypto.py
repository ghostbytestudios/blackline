"""AES-GCM + Argon2id primitives: round-trips, tamper rejection, key derivation."""

from __future__ import annotations

import pytest

from app.security import crypto

KEY = bytes(range(32))
OTHER_KEY = bytes(range(1, 33))


def test_encrypt_decrypt_round_trip():
    nonce, ct = crypto.encrypt(KEY, b"hello vault", aad=b"slot")
    assert crypto.decrypt(KEY, nonce, ct, aad=b"slot") == b"hello vault"


def test_nonce_is_fresh_per_encryption():
    n1, c1 = crypto.encrypt(KEY, b"same plaintext")
    n2, c2 = crypto.encrypt(KEY, b"same plaintext")
    assert n1 != n2
    assert c1 != c2


def test_wrong_key_rejected():
    nonce, ct = crypto.encrypt(KEY, b"secret")
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(OTHER_KEY, nonce, ct)


def test_tampered_ciphertext_rejected():
    nonce, ct = crypto.encrypt(KEY, b"secret")
    tampered = bytes([ct[0] ^ 0xFF]) + ct[1:]
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(KEY, nonce, tampered)


def test_aad_mismatch_rejected():
    """A ciphertext bound to one slot name must not decrypt under another."""
    nonce, ct = crypto.encrypt(KEY, b"secret", aad=b"slot-a")
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(KEY, nonce, ct, aad=b"slot-b")


def test_derive_key_deterministic_and_salt_sensitive():
    salt_a = b"\x01" * crypto.SALT_LEN
    salt_b = b"\x02" * crypto.SALT_LEN
    k1 = crypto.derive_key("correct horse battery", salt_a)
    k2 = crypto.derive_key("correct horse battery", salt_a)
    k3 = crypto.derive_key("correct horse battery", salt_b)
    k4 = crypto.derive_key("different passphrase", salt_a)
    assert len(k1) == crypto.KEY_LEN
    assert k1 == k2
    assert k1 != k3
    assert k1 != k4
