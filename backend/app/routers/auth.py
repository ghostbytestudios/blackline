"""Lock/unlock and status endpoints."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy import func, select

from .. import audit
from ..db import read_scope
from ..models import Account, AuditLog
from ..deps import require_unlocked
from ..schemas import ChangePassphraseRequest, ResetVaultRequest, StatusResponse, UnlockRequest
from ..security import vault
from ..security.lock import app_lock, unlock_throttle

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
    from ..services import demo

    with read_scope() as db:
        connected = vault.has_secret(db, vault.SIMPLEFIN_ACCESS_URL)
        account_count = int(db.scalar(select(func.count(Account.id))) or 0)
        demo_data = demo.has_demo_data(db)
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
        demo_data=demo_data,
    )


@router.get("/status", response_model=StatusResponse)
def status() -> StatusResponse:
    return build_status()


@router.post("/unlock", response_model=StatusResponse)
def unlock(body: UnlockRequest) -> StatusResponse:
    wait = unlock_throttle.retry_after()
    if wait > 0:
        seconds = math.ceil(wait)
        raise HTTPException(
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Try again in {seconds}s.",
            headers={"Retry-After": str(seconds)},
        )
    ok = app_lock.unlock(body.passphrase)
    if not ok:
        # Can't audit a failed unlock — the DB is still locked/undecryptable.
        unlock_throttle.record_failure()
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Incorrect passphrase."
        )
    unlock_throttle.reset()
    # DB is open now; record the successful unlock (commit persists the blob).
    with read_scope() as db:
        audit.record(db, "unlock", success=True)
    return build_status()


@router.post("/change-passphrase", response_model=StatusResponse)
def change_passphrase(
    body: ChangePassphraseRequest, _: None = Depends(require_unlocked)
) -> StatusResponse:
    ok = app_lock.change_passphrase(body.current_passphrase, body.new_passphrase)
    with read_scope() as db:
        audit.record(db, "change_passphrase", success=ok)
    if not ok:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Current passphrase is incorrect."
        )
    return build_status()


# The user must type this exact phrase in the UI to reset the vault.
RESET_CONFIRM_PHRASE = "DELETE MY DATA"


@router.post("/reset-vault", response_model=StatusResponse)
def reset_vault(body: ResetVaultRequest) -> StatusResponse:
    """Wipe the vault so a forgotten passphrase isn't a dead end.

    Deliberately works while locked — that is the whole point — guarded by a typed
    confirmation phrase. Without the passphrase the data is undecryptable anyway,
    so this destroys nothing an attacker could otherwise read; it only resets.
    No audit entry is possible: the audit log lives inside the destroyed vault.
    """
    if body.confirm != RESET_CONFIRM_PHRASE:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f'Confirmation phrase does not match. Type "{RESET_CONFIRM_PHRASE}" exactly.',
        )
    app_lock.reset_vault()
    unlock_throttle.reset()
    return build_status()


@router.post("/lock", response_model=StatusResponse)
def lock() -> StatusResponse:
    # Audit while still unlocked (the DB is encrypted/closed after locking).
    if app_lock.is_unlocked:
        with read_scope() as db:
            audit.record(db, "lock", success=True)
    app_lock.lock()
    return build_status()
