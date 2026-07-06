"""Station-type endpoints: admin-authored templates players build from.

Anyone signed in can list types (Commanders pick one when building). Admins
create/edit/delete them and upload the station's blueprint (parsed and stored
like a ship blueprint, but without validation rules — stations have none).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.enums import StationKind
from app.models.station import Station, StationType
from app.models.user import User
from app.schemas.station import StationTypeCreate, StationTypeOut, StationTypeUpdate
from app.services.seformat.blueprint import (
    BlueprintParseError,
    extract_bp_sbc,
    extract_thumbnail,
    parse_blueprint,
)
from app.services.storage import get_storage

router = APIRouter(prefix="/api/station-types", tags=["station-types"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _out(st: StationType) -> StationTypeOut:
    return StationTypeOut.model_validate(st)


@router.get("", response_model=list[StationTypeOut])
def list_station_types(
    db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    types = (
        db.execute(select(StationType).order_by(StationType.name)).scalars().all()
    )
    return [_out(t) for t in types]


@router.post("", response_model=StationTypeOut, status_code=status.HTTP_201_CREATED)
def create_station_type(
    payload: StationTypeCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    st = StationType(
        name=payload.name,
        kind=payload.kind,
        description=payload.description,
        cost={r.value: n for r, n in payload.cost.items() if n > 0},
        produced_resource=(
            payload.produced_resource if payload.kind == StationKind.resource else None
        ),
        production_amount=(
            payload.production_amount if payload.kind == StationKind.resource else 0
        ),
        build_slots=(
            payload.build_slots if payload.kind == StationKind.shipyard else 1
        ),
        created_by=admin.id,
    )
    db.add(st)
    db.commit()
    db.refresh(st)
    return _out(st)


@router.patch("/{type_id}", response_model=StationTypeOut)
def update_station_type(
    type_id: uuid.UUID,
    payload: StationTypeUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    st = db.get(StationType, type_id)
    if st is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station type not found")
    if payload.name is not None:
        st.name = payload.name
    if payload.description is not None:
        st.description = payload.description
    if payload.cost is not None:
        st.cost = {r.value: n for r, n in payload.cost.items() if n > 0}
    if st.kind == StationKind.resource:
        if payload.produced_resource is not None:
            st.produced_resource = payload.produced_resource
        if payload.production_amount is not None:
            st.production_amount = payload.production_amount
    if st.kind == StationKind.shipyard and payload.build_slots is not None:
        st.build_slots = payload.build_slots
    db.commit()
    db.refresh(st)
    return _out(st)


@router.delete("/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_station_type(
    type_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    st = db.get(StationType, type_id)
    if st is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station type not found")
    if st.is_starter:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The starter shipyard type cannot be deleted"
        )
    in_use = db.execute(
        select(Station.id).where(Station.station_type_id == type_id).limit(1)
    ).first()
    if in_use is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Station type is in use by built stations and cannot be deleted",
        )
    storage = get_storage()
    for key in (st.b2_key, st.thumb_b2_key):
        if key:
            try:
                storage.delete(key)
            except Exception:
                pass
    db.delete(st)
    db.commit()


@router.post("/{type_id}/blueprint", response_model=StationTypeOut)
def upload_station_blueprint(
    type_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Attach a station grid blueprint to a type: parse for stats/thumbnail, store."""
    st = db.get(StationType, type_id)
    if st is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station type not found")

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

    storage = get_storage()
    b2_key = f"station-blueprints/{st.id}.zip"
    storage.put(b2_key, raw, content_type="application/zip")

    thumb_key = None
    thumb = extract_thumbnail(raw)
    if thumb is not None:
        thumb_key = f"station-blueprints/{st.id}-thumb.png"
        storage.put(thumb_key, thumb, content_type="image/png")

    st.b2_key = b2_key
    st.thumb_b2_key = thumb_key
    st.stats = {
        "block_count": parsed.block_count,
        "grid_sizes": sorted(parsed.grid_sizes),
        "display_name": parsed.display_name,
    }
    db.commit()
    db.refresh(st)
    return _out(st)


@router.get("/{type_id}/thumbnail")
def station_thumbnail(
    type_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    st = db.get(StationType, type_id)
    if st is None or not st.thumb_b2_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No thumbnail")
    try:
        data = get_storage().get(st.thumb_b2_key)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No thumbnail") from exc
    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )
