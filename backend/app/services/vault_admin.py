"""Data-safety plumbing: rotated-backup listing and portable vault bundles.

Everything here handles ciphertext only — the encrypted blob and the KDF salt.
Nothing in this module can decrypt anything; the passphrase never appears.
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import UTC, datetime
from pathlib import Path

from ..config import get_settings
from ..security import crypto

BUNDLE_FORMAT = "blackline-vault"
BUNDLE_VERSION = 1


class BackupNotFound(Exception):
    """Raised when a requested backup name doesn't resolve to a rotated backup."""


class BundleError(Exception):
    """Raised when an export bundle is malformed or incompatible with this install."""


def list_backups() -> list[dict]:
    """Rotated encrypted-blob backups, newest first."""
    settings = get_settings()
    if not settings.backup_dir.exists():
        return []
    out = []
    for p in sorted(settings.backup_dir.glob(f"{settings.db_enc_path.name}.*.bak"), reverse=True):
        st = p.stat()
        out.append(
            {
                "name": p.name,
                "created_at": datetime.fromtimestamp(st.st_mtime, UTC),
                "size_bytes": st.st_size,
            }
        )
    return out


def backup_path(name: str) -> Path:
    """Resolve a bare backup filename inside the backup dir.

    The name comes from the API, so anything path-like (separators, traversal) or
    not shaped like a rotated backup is rejected outright.
    """
    settings = get_settings()
    path = settings.backup_dir / name
    if (
        name != Path(name).name
        or not name.startswith(settings.db_enc_path.name + ".")
        or not name.endswith(".bak")
        or not path.is_file()
    ):
        raise BackupNotFound(name)
    return path


def export_bundle() -> str:
    """Bundle the salt + encrypted blob into one portable JSON document.

    The KDF parameters ride along so an import on another machine can detect a
    mismatch (a different Argon2 configuration would derive a different key from
    the same passphrase, making the blob silently undecryptable).
    """
    settings = get_settings()
    doc = {
        "format": BUNDLE_FORMAT,
        "version": BUNDLE_VERSION,
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "cipher": "aes-256-gcm",
        "kdf": {
            "algorithm": "argon2id",
            "time_cost": settings.argon2_time_cost,
            "memory_kib": settings.argon2_memory_kib,
            "parallelism": settings.argon2_parallelism,
        },
        "salt_b64": base64.b64encode(settings.salt_path.read_bytes()).decode(),
        "blob_b64": base64.b64encode(settings.db_enc_path.read_bytes()).decode(),
    }
    return json.dumps(doc)


def parse_bundle(text: str) -> tuple[bytes, bytes]:
    """Validate an export bundle and return (salt, blob). Raises BundleError."""
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BundleError("Not a Blackline vault export (invalid JSON).") from exc
    if not isinstance(doc, dict) or doc.get("format") != BUNDLE_FORMAT:
        raise BundleError("Not a Blackline vault export.")
    if doc.get("version") != BUNDLE_VERSION:
        raise BundleError(f"Unsupported export version {doc.get('version')!r}.")
    try:
        salt = base64.b64decode(doc["salt_b64"], validate=True)
        blob = base64.b64decode(doc["blob_b64"], validate=True)
    except (KeyError, TypeError, binascii.Error) as exc:
        raise BundleError("Export file is corrupted (bad payload encoding).") from exc
    if len(salt) != crypto.SALT_LEN or len(blob) <= crypto.NONCE_LEN:
        raise BundleError("Export file is corrupted (payload sizes are wrong).")

    settings = get_settings()
    ours = {
        "time_cost": settings.argon2_time_cost,
        "memory_kib": settings.argon2_memory_kib,
        "parallelism": settings.argon2_parallelism,
    }
    kdf = doc.get("kdf") if isinstance(doc.get("kdf"), dict) else {}
    theirs = {k: kdf.get(k) for k in ours}
    if theirs != ours:
        raise BundleError(
            "This export was made with different key-derivation settings than this "
            f"install uses ({theirs} vs {ours}). Set the matching BLACKLINE_ARGON2_* "
            "values before importing."
        )
    return salt, blob
