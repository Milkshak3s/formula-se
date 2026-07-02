from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.schemas.admin import BlockDataRefreshResult, BlockDataStats
from app.services.blockdata import block_data_stats, parse_upload, upsert_block_defs

router = APIRouter(prefix="/api/block-definitions", tags=["block-definitions"])


@router.get("", response_model=BlockDataStats)
def get_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return block_data_stats(db)


@router.post("", response_model=BlockDataRefreshResult, status_code=status.HTTP_201_CREATED)
def refresh(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    raw = file.file.read()
    defs = parse_upload(raw)
    source = f"upload:{file.filename or 'cubeblocks'}"
    n = upsert_block_defs(db, defs, source=source)
    return BlockDataRefreshResult(parsed=len(defs), upserted=n, source=source)
