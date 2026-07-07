"""Station endpoints: list built stations, and (Commander) build one on a sector.

Building charges the shared campaign treasury for the station type's cost and
places the station on a hex tile. The future gates — build only in sectors you
own or have ships in — are deliberately not enforced here.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin, require_commander
from app.models.hexmap import HexTile
from app.models.station import Station, StationType
from app.models.user import User
from app.schemas.station import StationBuild, StationOut
from app.services.stations import (
    InsufficientResources,
    StationLimitReached,
    build_station,
)

router = APIRouter(prefix="/api/stations", tags=["stations"])


def _out(station: Station, builder_name: str | None) -> StationOut:
    st = station.station_type
    tile = station.hex_tile
    return StationOut(
        id=station.id,
        hex_tile_id=station.hex_tile_id,
        q=tile.q,
        r=tile.r,
        station_type_id=station.station_type_id,
        station_type_name=st.name,
        kind=st.kind,
        produced_resource=st.produced_resource,
        production_amount=st.production_amount,
        build_slots=st.build_slots,
        built_by=station.built_by,
        built_by_name=builder_name,
        built_on_turn=station.built_on_turn,
        created_at=station.created_at,
    )


def _names_for(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    rows = db.execute(
        select(User.id, User.display_name).where(User.id.in_(ids))
    ).all()
    return {uid: name for uid, name in rows}


@router.get("", response_model=list[StationOut])
def list_stations(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stations = (
        db.execute(
            select(Station)
            .options(
                selectinload(Station.station_type),
                selectinload(Station.hex_tile),
            )
            .order_by(Station.created_at)
        )
        .scalars()
        .all()
    )
    names = _names_for(db, {s.built_by for s in stations if s.built_by})
    return [_out(s, names.get(s.built_by)) for s in stations]


@router.post("", response_model=StationOut, status_code=status.HTTP_201_CREATED)
def build(
    payload: StationBuild,
    db: Session = Depends(get_db),
    user: User = Depends(require_commander),
):
    tile = db.get(HexTile, payload.hex_tile_id)
    if tile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sector not found")
    station_type = db.get(StationType, payload.station_type_id)
    if station_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station type not found")
    if station_type.is_starter:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "The starter shipyard is a campaign gift and cannot be built",
        )

    try:
        station = build_station(db, tile, station_type, user)
    except StationLimitReached as exc:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except InsufficientResources as exc:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    db.commit()
    # Re-load with relationships for serialization.
    station = db.execute(
        select(Station)
        .options(
            selectinload(Station.station_type), selectinload(Station.hex_tile)
        )
        .where(Station.id == station.id)
    ).scalar_one()
    return _out(station, user.display_name)


@router.delete("/{station_id}", status_code=status.HTTP_204_NO_CONTENT)
def demolish(
    station_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Remove a built station (admin cleanup). No resource refund."""
    station = db.get(Station, station_id)
    if station is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Station not found")
    db.delete(station)
    db.commit()
