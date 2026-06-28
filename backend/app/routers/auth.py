"""Lock/unlock and status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status as http_status
from sqlalchemy import func, select

from .. import audit
from ..db import read_scope
from ..models import Account, AuditLog
from ..schemas import StatusResponse, UnlockRequest
from ..security import vault
from ..security.lock import app_lock

router = APIRouter(tags=["auth"])


def build_status() -> StatusResponse:
    """Status works whether locked or unlocked. When locked, no DB is touched."""
    if not app_lock.is_unlocked:
        return StatusResponse(
            initialized=app_lock.is_initialized,
            unlocked=False,
            connected=False,
            account_count=0,
            last_sync=None,
        )
    with read_scope() as db:
        connected = vault.has_secret(db, vault.SIMPLEFIN_ACCESS_URL)
        account_count = int(db.scalar(select(func.count(Account.id))) or 0)
        last_sync = db.scalar(
            select(func.max(AuditLog.at)).where(
                AuditLog.event == "sync", AuditLog.success.is_(True)
            )
        )
    return StatusResponse(
        initialized=app_lock.is_initialized,
        unlocked=True,
        connected=connected,
        account_count=account_count,
        last_sync=last_sync,
    )


@router.get("/status", response_model=StatusResponse)
def status() -> StatusResponse:
    return build_status()


@router.post("/unlock", response_model=StatusResponse)
def unlock(body: UnlockRequest) -> StatusResponse:
    ok = app_lock.unlock(body.passphrase)
    if not ok:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Incorrect passphrase."
        )
    # DB is open now; record the successful unlock (commit persists the blob).
    with read_scope() as db:
        audit.record(db, "unlock", success=True)
    return build_status()


@router.post("/lock", response_model=StatusResponse)
def lock() -> StatusResponse:
    # Audit while still unlocked (the DB is encrypted/closed after locking).
    if app_lock.is_unlocked:
        with read_scope() as db:
            audit.record(db, "lock", success=True)
    app_lock.lock()
    return build_status()
