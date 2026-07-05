"""Sector-map endpoints: read the hex grid, and (admin) reshape/annotate it.

The map is the campaign board. Reading is open to any signed-in user (future
Commander views of stations/ships render on top of this); reshaping the grid or
labelling sectors is an admin authoring action.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.hexmap import HexMap, HexTile
from app.models.user import User
from app.schemas.hexmap import HexMapOut, HexMapRegenerate, HexTileOut, HexTileUpdate
from app.services.hexmap import ensure_tiles, generate_tiles, get_map

router = APIRouter(prefix="/api/hex-map", tags=["hex-map"])


def _map_out(db: Session, m: HexMap) -> HexMapOut:
    tiles = (
        db.execute(select(HexTile).order_by(HexTile.r, HexTile.q))
        .scalars()
        .all()
    )
    return HexMapOut(
        id=m.id,
        name=m.name,
        radius=m.radius,
        tiles=[HexTileOut.model_validate(t) for t in tiles],
    )


@router.get("", response_model=HexMapOut)
def get_hex_map(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    # Lazily materialise the default grid if it has never been generated.
    ensure_tiles(db)
    return _map_out(db, get_map(db))


@router.post("/regenerate", response_model=HexMapOut)
def regenerate(
    payload: HexMapRegenerate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    m = get_map(db)
    if payload.name is not None:
        m.name = payload.name
    generate_tiles(db, payload.radius)
    db.commit()
    return _map_out(db, get_map(db))


@router.patch("/tiles/{tile_id}", response_model=HexTileOut)
def update_tile(
    tile_id: uuid.UUID,
    payload: HexTileUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    tile = db.get(HexTile, tile_id)
    if tile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tile not found")
    if payload.terrain is not None:
        tile.terrain = payload.terrain
    if payload.name is not None:
        tile.name = payload.name
    db.commit()
    db.refresh(tile)
    return HexTileOut.model_validate(tile)
