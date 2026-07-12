"""Audit-log viewer, backup restore, and portable vault export/import."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db, read_scope
from ..deps import require_unlocked
from ..models import AuditLog
from ..schemas import (
    AuditPageOut,
    BackupOut,
    RestoreBackupRequest,
    StatusResponse,
    VaultImportRequest,
)
from ..security import crypto
from ..security.lock import app_lock, unlock_throttle
from ..services import vault_admin
from .auth import build_status

router = APIRouter(tags=["system"])


@router.get("/audit", response_model=AuditPageOut, dependencies=[Depends(require_unlocked)])
def audit_log(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> AuditPageOut:
    """The local audit trail, newest first."""
    total = int(db.scalar(select(func.count(AuditLog.id))) or 0)
    items = db.scalars(
        select(AuditLog)
        .order_by(AuditLog.at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return AuditPageOut(total=total, items=items)


@router.get(
    "/backups", response_model=list[BackupOut], dependencies=[Depends(require_unlocked)]
)
def list_backups() -> list[BackupOut]:
    return [BackupOut(**b) for b in vault_admin.list_backups()]


# The user must type this exact phrase in the UI to restore a backup.
RESTORE_CONFIRM_PHRASE = "RESTORE BACKUP"


@router.post(
    "/backups/restore",
    response_model=StatusResponse,
    dependencies=[Depends(require_unlocked)],
)
def restore_backup(body: RestoreBackupRequest) -> StatusResponse:
    """Swap the vault for a rotated backup (the current state is snapshotted first)."""
    if body.confirm != RESTORE_CONFIRM_PHRASE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Confirmation phrase does not match. Type "{RESTORE_CONFIRM_PHRASE}" exactly.',
        )
    try:
        path = vault_admin.backup_path(body.name)
    except vault_admin.BackupNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such backup."
        ) from None
    try:
        app_lock.restore_backup(path)
    except crypto.DecryptionError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This backup was written under a different passphrase and can't be "
            "restored with the current one.",
        ) from None
    with read_scope() as db:
        audit.record(db, "restore_backup", detail=body.name)
    return build_status()


@router.get("/vault/export", dependencies=[Depends(require_unlocked)])
def export_vault() -> Response:
    """Download the whole vault as one portable file (salt + encrypted blob).

    Ciphertext only — unlocking it anywhere requires the passphrase. Audit first:
    the audit commit re-persists the blob, so the bundle must be read after it.
    """
    with read_scope() as db:
        audit.record(db, "vault_export")
    text = vault_admin.export_bundle()
    fname = f"blackline-vault-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.blackline"
    return Response(
        content=text,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# The user must type this exact phrase to replace an existing vault on import.
IMPORT_CONFIRM_PHRASE = "REPLACE MY DATA"


@router.post("/vault/import", response_model=StatusResponse)
def import_vault(body: VaultImportRequest) -> StatusResponse:
    """Install an exported bundle as the vault. Deliberately works while locked —
    this is the lock-screen "move machines" flow.

    Replacing an existing vault is destructive, so it takes a typed-phrase guard
    like reset. No audit entry is possible: the app ends up locked and the imported
    vault's key is unknown until its passphrase is entered.
    """
    if app_lock.is_initialized and body.confirm != IMPORT_CONFIRM_PHRASE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'A vault already exists here. Type "{IMPORT_CONFIRM_PHRASE}" exactly to replace it.',
        )
    try:
        salt, blob = vault_admin.parse_bundle(body.bundle)
    except vault_admin.BundleError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    app_lock.import_vault(salt, blob)
    unlock_throttle.reset()
    return build_status()
