from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.world import GameMap, StartSlot, StartSlotClass
from app.models.user import User
from app.schemas.world import MapOut, MapUpdate, StartSlotIn
from app.services.seformat.gps import parse_gps
from app.services.storage import get_storage

router = APIRouter(prefix="/api/maps", tags=["maps"])

MAX_MAP_BYTES = 500 * 1024 * 1024  # 500 MB


def _serialize_map(m: GameMap) -> dict:
    return {
        "id": m.id,
        "name": m.name,
        "description": m.description,
        "created_at": m.created_at,
        "start_slots": [
            {
                "id": s.id,
                "map_id": s.map_id,
                "name": s.name,
                "position_index": s.position_index,
                "gps_x": s.gps_x,
                "gps_y": s.gps_y,
                "gps_z": s.gps_z,
                "ship_class_ids": [c.ship_class_id for c in s.supported_classes],
            }
            for s in m.start_slots
        ],
    }


def _load(db: Session, map_id: uuid.UUID) -> GameMap:
    m = db.execute(
        select(GameMap)
        .options(
            selectinload(GameMap.start_slots).selectinload(StartSlot.supported_classes)
        )
        .where(GameMap.id == map_id)
    ).scalar_one_or_none()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Map not found")
    return m


def _resolve_coords(slot_in: StartSlotIn) -> tuple[float, float, float]:
    if slot_in.gps_string:
        parsed = parse_gps(slot_in.gps_string)
        return parsed.x, parsed.y, parsed.z
    if slot_in.gps_x is None or slot_in.gps_y is None or slot_in.gps_z is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Start slot '{slot_in.name}' needs a GPS string or explicit X/Y/Z",
        )
    return slot_in.gps_x, slot_in.gps_y, slot_in.gps_z


@router.get("", response_model=list[MapOut])
def list_maps(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    maps = (
        db.execute(
            select(GameMap)
            .options(
                selectinload(GameMap.start_slots).selectinload(
                    StartSlot.supported_classes
                )
            )
            .order_by(GameMap.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_serialize_map(m) for m in maps]


@router.post("", response_model=MapOut, status_code=status.HTTP_201_CREATED)
def create_map(
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    raw = file.file.read()
    if len(raw) > MAX_MAP_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Map upload too large")

    m = GameMap(name=name, description=description, b2_key="", uploaded_by=admin.id)
    db.add(m)
    db.flush()  # assign id
    key = f"maps/{m.id}.zip"
    get_storage().put(key, raw, content_type="application/zip")
    m.b2_key = key
    db.commit()
    return _serialize_map(_load(db, m.id))


@router.patch("/{map_id}", response_model=MapOut)
def update_map(
    map_id: uuid.UUID,
    payload: MapUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    m = _load(db, map_id)
    if payload.name is not None:
        m.name = payload.name
    if payload.description is not None:
        m.description = payload.description
    if payload.start_slots is not None:
        # Replace the full start-slot set.
        m.start_slots.clear()
        db.flush()
        for idx, slot_in in enumerate(payload.start_slots):
            x, y, z = _resolve_coords(slot_in)
            slot = StartSlot(
                map_id=m.id,
                name=slot_in.name,
                position_index=slot_in.position_index or idx,
                gps_x=x,
                gps_y=y,
                gps_z=z,
            )
            for cid in slot_in.ship_class_ids:
                slot.supported_classes.append(StartSlotClass(ship_class_id=cid))
            m.start_slots.append(slot)
    db.commit()
    return _serialize_map(_load(db, map_id))


@router.delete("/{map_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_map(
    map_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    m = _load(db, map_id)
    storage = get_storage()
    if m.b2_key:
        try:
            storage.delete(m.b2_key)
        except Exception:
            pass
    db.delete(m)
    db.commit()
