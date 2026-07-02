from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_commander
from app.models.enums import BlueprintStatus, PreparedWorldStatus
from app.models.ship import BlueprintSlot
from app.models.user import User
from app.models.world import (
    GameMap,
    PreparedWorld,
    PreparedWorldAssignment,
    StartSlot,
    StartSlotClass,
)
from app.schemas.world import PreparedWorldCreate, PreparedWorldOut
from app.services.deliverers import get_deliverer
from app.services.jobs import JOB_PREPARE_WORLD, enqueue
from app.services.settings_store import get_server_push_enabled
from app.services.storage import get_storage

router = APIRouter(prefix="/api/prepared-worlds", tags=["prepared-worlds"])


@router.get("", response_model=list[PreparedWorldOut])
def list_prepared(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return (
        db.execute(select(PreparedWorld).order_by(PreparedWorld.created_at.desc()))
        .scalars()
        .all()
    )


@router.get("/{pw_id}", response_model=PreparedWorldOut)
def get_prepared(
    pw_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    pw = db.get(PreparedWorld, pw_id)
    if pw is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prepared world not found")
    return pw


@router.post("", response_model=PreparedWorldOut, status_code=status.HTTP_201_CREATED)
def create_prepared(
    payload: PreparedWorldCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_commander),
):
    game_map = db.execute(
        select(GameMap)
        .options(
            selectinload(GameMap.start_slots).selectinload(StartSlot.supported_classes)
        )
        .where(GameMap.id == payload.map_id)
    ).scalar_one_or_none()
    if game_map is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Map not found")

    start_slots = {s.id: s for s in game_map.start_slots}

    pw = PreparedWorld(
        map_id=game_map.id,
        name=payload.name,
        created_by=user.id,
        status=PreparedWorldStatus.queued,
    )
    db.add(pw)
    db.flush()

    for assignment in payload.assignments:
        if assignment.slot_id is None:
            continue
        start_slot = start_slots.get(assignment.start_slot_id)
        if start_slot is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Start slot {assignment.start_slot_id} not on this map",
            )
        slot = db.execute(
            select(BlueprintSlot)
            .options(selectinload(BlueprintSlot.blueprints))
            .where(BlueprintSlot.id == assignment.slot_id)
        ).scalar_one_or_none()
        if slot is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Blueprint slot not found")

        active_bp = slot.active_blueprint
        if active_bp is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Slot '{slot.name}' has no blueprint to assign",
            )

        supported = {c.ship_class_id for c in start_slot.supported_classes}
        if slot.ship_class_id not in supported:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Slot '{slot.name}' class not supported by start slot '{start_slot.name}'",
            )

        db.add(
            PreparedWorldAssignment(
                prepared_world_id=pw.id,
                start_slot_id=start_slot.id,
                blueprint_id=active_bp.id,
            )
        )

    db.commit()
    enqueue(db, JOB_PREPARE_WORLD, {"prepared_world_id": str(pw.id)})
    db.refresh(pw)
    return pw


@router.get("/{pw_id}/download")
def download_prepared(
    pw_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    pw = db.get(PreparedWorld, pw_id)
    if pw is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prepared world not found")
    if pw.status != PreparedWorldStatus.ready or not pw.b2_key:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Prepared world is not ready ({pw.status.value})"
        )
    storage = get_storage()
    return {
        "url": storage.presigned_url(pw.b2_key, download_name=f"{pw.name}.zip")
    }


@router.post("/{pw_id}/deliver")
def deliver_prepared(
    pw_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_commander),
):
    if not get_server_push_enabled(db):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Server push is disabled"
        )
    pw = db.get(PreparedWorld, pw_id)
    if pw is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prepared world not found")
    if pw.status != PreparedWorldStatus.ready or not pw.b2_key:
        raise HTTPException(status.HTTP_409_CONFLICT, "Prepared world is not ready")
    result = get_deliverer().deliver(str(pw.id), pw.b2_key, f"{pw.name}.zip")
    return {"delivered": result.delivered, "detail": result.detail}
