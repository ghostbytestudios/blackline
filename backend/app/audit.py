"""Local audit logging for sensitive operations."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import AuditLog


def record(db: Session, event: str, detail: str = "", success: bool = True) -> None:
    """Append an audit entry. `detail` must never contain secrets/credentials."""
    db.add(AuditLog(event=event, detail=detail[:1000], success=success))
    db.commit()
