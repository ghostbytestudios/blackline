"""Connect a SimpleFIN account and trigger syncs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import require_unlocked
from ..integrations import simplefin
from ..schemas import SetupTokenRequest, StatusResponse, SyncResult
from ..security import vault
from ..security.lock import app_lock
from ..services import sync as sync_service
from .auth import build_status

router = APIRouter(tags=["connect"], dependencies=[Depends(require_unlocked)])


@router.post("/connect", response_model=StatusResponse)
def connect(body: SetupTokenRequest, db: Session = Depends(get_db)) -> StatusResponse:
    """Exchange a one-time SimpleFIN setup token for a read-only access URL and store it."""
    try:
        access_url = simplefin.claim_access_url(body.setup_token)
    except simplefin.SimpleFINError as exc:
        audit.record(db, "connect", detail=str(exc), success=False)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    key = app_lock.require_key()
    vault.put_secret(db, key, vault.SIMPLEFIN_ACCESS_URL, access_url.encode("utf-8"))
    audit.record(db, "connect", detail="access url stored", success=True)
    return build_status()


@router.delete("/connect", response_model=StatusResponse)
def disconnect(db: Session = Depends(get_db)) -> StatusResponse:
    """Remove the stored SimpleFIN access URL (does not delete already-synced data)."""
    from sqlalchemy import delete

    from ..models import Secret

    db.execute(delete(Secret).where(Secret.name == vault.SIMPLEFIN_ACCESS_URL))
    db.commit()
    audit.record(db, "disconnect", success=True)
    return build_status()


@router.post("/sync", response_model=SyncResult)
def sync(lookback_days: int = 90, db: Session = Depends(get_db)) -> SyncResult:
    lookback_days = max(1, min(lookback_days, 730))
    try:
        return sync_service.run_sync(db, lookback_days=lookback_days)
    except simplefin.SimpleFINError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
