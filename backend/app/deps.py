"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import HTTPException, status

from .security.lock import app_lock


def require_unlocked() -> None:
    """Guard dependency: 423 Locked if the vault isn't unlocked."""
    if not app_lock.is_unlocked:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Application is locked. Unlock with your passphrase.",
        )
