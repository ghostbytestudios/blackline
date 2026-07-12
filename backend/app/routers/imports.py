"""Statement import endpoints (CSV/OFX).

Two-step flow: /import/preview parses the uploaded text and suggests a column
mapping; /import/commit re-parses with the user's final mapping and inserts.
The frontend holds the file between steps — nothing is cached server-side.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit
from ..db import get_db
from ..deps import require_unlocked
from ..models import Account
from ..schemas import ImportCommitRequest, ImportPreview, ImportPreviewRequest, ImportResult
from ..services import importer

router = APIRouter(tags=["import"], dependencies=[Depends(require_unlocked)])


@router.post("/import/preview", response_model=ImportPreview)
def preview_import(body: ImportPreviewRequest) -> ImportPreview:
    try:
        return importer.build_preview(body.filename, body.content)
    except importer.ImportError_ as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post("/import/commit", response_model=ImportResult)
def commit_import(body: ImportCommitRequest, db: Session = Depends(get_db)) -> ImportResult:
    account = db.get(Account, body.account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    try:
        parsed = importer.parse_file(body.filename, body.content, body.mapping)
        result = importer.commit_import(
            db, account, parsed, skip_duplicates=body.skip_duplicates
        )
    except importer.ImportError_ as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    audit.record(
        db,
        "import",
        detail=(
            f"file={body.filename} account={account.id} "
            f"inserted={result.inserted} dup={result.duplicates_skipped}"
        ),
    )
    return result
