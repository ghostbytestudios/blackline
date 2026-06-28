"""Lock/unlock and status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..models import Account, AuditLog
from ..schemas import StatusResponse, UnlockRequest
from ..security import vault
from ..security.lock import app_lock

router = APIRouter(tags=["auth"])


@router.get("/status", response_model=StatusResponse)
def status(db: Session = Depends(get_db)) -> StatusResponse:
    unlocked = app_lock.is_unlocked
    connected = unlocked and vault.has_secret(db, vault.SIMPLEFIN_ACCESS_URL)
    account_count = db.scalar(select(func.count(Account.id))) or 0
    last_sync = db.scalar(
        select(func.max(AuditLog.at)).where(AuditLog.event == "sync", AuditLog.success.is_(True))
    )
    return StatusResponse(
        initialized=app_lock.is_initialized,
        unlocked=unlocked,
        connected=connected,
        account_count=int(account_count),
        last_sync=last_sync,
    )


@router.post("/unlock", response_model=StatusResponse)
def unlock(body: UnlockRequest, db: Session = Depends(get_db)) -> StatusResponse:
    from fastapi import HTTPException, status as http_status

    ok = app_lock.unlock(body.passphrase)
    audit.record(db, "unlock", success=ok)
    if not ok:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Incorrect passphrase."
        )
    return status(db)


@router.post("/lock", response_model=StatusResponse)
def lock(db: Session = Depends(get_db)) -> StatusResponse:
    app_lock.lock()
    audit.record(db, "lock", success=True)
    return status(db)
