from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin, require_engineer
from app.models.enums import BlueprintStatus
from app.models.ship import Blueprint, BlueprintSlot, ShipClass
from app.models.user import User
from app.schemas.ship import BlueprintOut, SlotCreate, SlotOut
from app.services.blockdata import build_lookup
from app.services.seformat.blueprint import (
    BlueprintParseError,
    extract_bp_sbc,
    extract_thumbnail,
    parse_blueprint,
)
from app.services.storage import get_storage
from app.services.validation.engine import RequirementSpec, validate_blueprint

router = APIRouter(prefix="/api/slots", tags=["slots"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _serialize_slot(slot: BlueprintSlot) -> dict:
    active = slot.active_blueprint
    return {
        "id": slot.id,
        "ship_class_id": slot.ship_class_id,
        "name": slot.name,
        "created_at": slot.created_at,
        "ship_class_name": slot.ship_class.name if slot.ship_class else None,
        "active_blueprint": (
            BlueprintOut.model_validate(active).model_dump() if active else None
        ),
    }


@router.get("", response_model=list[SlotOut])
def list_slots(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    slots = (
        db.execute(
            select(BlueprintSlot)
            .options(
                selectinload(BlueprintSlot.ship_class),
                selectinload(BlueprintSlot.blueprints),
            )
            .order_by(BlueprintSlot.name)
        )
        .scalars()
        .all()
    )
    return [_serialize_slot(s) for s in slots]


@router.post("", response_model=SlotOut, status_code=status.HTTP_201_CREATED)
def create_slot(
    payload: SlotCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    ship_class = db.get(ShipClass, payload.ship_class_id)
    if ship_class is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ship class not found")
    slot = BlueprintSlot(
        ship_class_id=payload.ship_class_id, name=payload.name, created_by=admin.id
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return _serialize_slot(slot)


@router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_slot(
    slot_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    slot = db.get(BlueprintSlot, slot_id)
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Slot not found")
    db.delete(slot)
    db.commit()


@router.post("/{slot_id}/blueprint")
def upload_blueprint(
    slot_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_engineer),
):
    """Upload a blueprint into a slot: parse → validate → store on success.

    Returns 201 with stats on success, or 422 with a per-rule validation report.
    """
    slot = db.execute(
        select(BlueprintSlot)
        .options(
            selectinload(BlueprintSlot.ship_class).selectinload(ShipClass.requirements),
            selectinload(BlueprintSlot.blueprints),
        )
        .where(BlueprintSlot.id == slot_id)
    ).scalar_one_or_none()
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Slot not found")

    raw = file.file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Blueprint upload too large"
        )

    try:
        bp_sbc = extract_bp_sbc(raw, file.filename or "")
        parsed = parse_blueprint(bp_sbc)
    except BlueprintParseError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    lookup = build_lookup(db)
    specs = [
        RequirementSpec(rule_type=r.rule_type, params=r.params)
        for r in slot.ship_class.requirements
    ]
    report = validate_blueprint(parsed, specs, lookup)

    if not report.passed:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=report.to_dict()
        )

    # Persist: store file, thumbnail, and mark prior active blueprint replaced.
    storage = get_storage()
    bp_id = uuid.uuid4()
    b2_key = f"blueprints/{slot.id}/{bp_id}.zip"
    storage.put(b2_key, raw, content_type="application/zip")

    thumb_key = None
    thumb = extract_thumbnail(raw)
    if thumb is not None:
        thumb_key = f"blueprints/{slot.id}/{bp_id}-thumb.png"
        storage.put(thumb_key, thumb, content_type="image/png")

    for prior in slot.blueprints:
        if prior.status == BlueprintStatus.active:
            prior.status = BlueprintStatus.replaced

    blueprint = Blueprint(
        id=bp_id,
        slot_id=slot.id,
        uploader_id=user.id,
        name=parsed.display_name or file.filename or slot.name,
        b2_key=b2_key,
        thumb_b2_key=thumb_key,
        stats=report.stats,
        status=BlueprintStatus.active,
    )
    db.add(blueprint)
    db.commit()
    db.refresh(blueprint)

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "passed": True,
            "blueprint": BlueprintOut.model_validate(blueprint).model_dump(mode="json"),
            "report": report.to_dict(),
        },
    )


@router.delete("/{slot_id}/blueprint", status_code=status.HTTP_204_NO_CONTENT)
def clear_slot(
    slot_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    slot = db.execute(
        select(BlueprintSlot)
        .options(selectinload(BlueprintSlot.blueprints))
        .where(BlueprintSlot.id == slot_id)
    ).scalar_one_or_none()
    if slot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Slot not found")
    for bp in slot.blueprints:
        if bp.status == BlueprintStatus.active:
            bp.status = BlueprintStatus.cleared
    db.commit()
