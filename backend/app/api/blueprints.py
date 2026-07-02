from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.ship import Blueprint
from app.models.user import User
from app.schemas.ship import BlueprintOut
from app.services.storage import get_storage

router = APIRouter(prefix="/api/blueprints", tags=["blueprints"])


@router.get("/{blueprint_id}", response_model=BlueprintOut)
def get_blueprint(
    blueprint_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    bp = db.get(Blueprint, blueprint_id)
    if bp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blueprint not found")
    return bp


@router.get("/{blueprint_id}/download")
def download_blueprint(
    blueprint_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    bp = db.get(Blueprint, blueprint_id)
    if bp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Blueprint not found")
    storage = get_storage()
    name = f"{bp.name or 'blueprint'}.zip"
    return {"url": storage.presigned_url(bp.b2_key, download_name=name)}
