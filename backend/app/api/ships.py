"""Ship endpoints: the shared ship stock and the shipyard build queue.

Two concerns, two routers:

* ``/api/ships`` — the campaign's shared stock of completed ships (list for any
  user; admin manual grant + removal).
* ``/api/ship-builds`` — in-progress build orders (list for any user; Commander
  queue + cancel). Queuing charges the treasury for the class's cost and is
  capped by the shipyard's build slots; cancelling frees a slot with no refund.

Kept as separate top-level prefixes so ``/{id}`` paths never shadow the build
routes.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin, require_commander
from app.models.hexmap import HexTile
from app.models.ship import Ship, ShipBuildOrder, ShipClass
from app.models.station import Station
from app.models.user import User
from app.schemas.ship import (
    ShipBuildCreate,
    ShipBuildOrderOut,
    ShipCreate,
    ShipOut,
)
from app.services.ships import (
    InsufficientResources,
    NotAShipyard,
    ShipyardFull,
    add_ship,
    queue_build,
)

ships_router = APIRouter(prefix="/api/ships", tags=["ships"])
builds_router = APIRouter(prefix="/api/ship-builds", tags=["ship-builds"])


def _names_for(db: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = db.execute(
        select(User.id, User.display_name).where(User.id.in_(ids))
    ).all()
    return {uid: name for uid, name in rows}


def _ship_out(ship: Ship, builder_name: str | None) -> ShipOut:
    return ShipOut(
        id=ship.id,
        ship_class_id=ship.ship_class_id,
        ship_class_name=ship.ship_class.name,
        hex_tile_id=ship.hex_tile_id,
        q=ship.hex_tile.q,
        r=ship.hex_tile.r,
        built_by=ship.built_by,
        built_by_name=builder_name,
        built_on_turn=ship.built_on_turn,
        created_at=ship.created_at,
    )


def _order_out(order: ShipBuildOrder, queuer_name: str | None) -> ShipBuildOrderOut:
    tile = order.shipyard.hex_tile
    return ShipBuildOrderOut(
        id=order.id,
        shipyard_id=order.shipyard_id,
        q=tile.q,
        r=tile.r,
        ship_class_id=order.ship_class_id,
        ship_class_name=order.ship_class.name,
        turns_remaining=order.turns_remaining,
        build_time=order.ship_class.build_time,
        queued_by=order.queued_by,
        queued_by_name=queuer_name,
        queued_on_turn=order.queued_on_turn,
        created_at=order.created_at,
    )


# --- shared ship stock ---
@ships_router.get("", response_model=list[ShipOut])
def list_ships(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    ships = (
        db.execute(
            select(Ship)
            .options(
                selectinload(Ship.ship_class), selectinload(Ship.hex_tile)
            )
            .order_by(Ship.created_at)
        )
        .scalars()
        .all()
    )
    names = _names_for(db, {s.built_by for s in ships})
    return [_ship_out(s, names.get(s.built_by)) for s in ships]


@ships_router.post("", response_model=ShipOut, status_code=status.HTTP_201_CREATED)
def grant_ship(
    payload: ShipCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin: place a ship of a class into shared stock at a chosen sector."""
    ship_class = db.get(ShipClass, payload.ship_class_id)
    if ship_class is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ship class not found")
    tile = db.get(HexTile, payload.hex_tile_id)
    if tile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sector not found")

    ship = add_ship(db, ship_class, tile.id, admin)
    db.commit()
    ship = db.execute(
        select(Ship)
        .options(selectinload(Ship.ship_class), selectinload(Ship.hex_tile))
        .where(Ship.id == ship.id)
    ).scalar_one()
    return _ship_out(ship, admin.display_name)


@ships_router.delete("/{ship_id}", status_code=status.HTTP_204_NO_CONTENT)
def scrap_ship(
    ship_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin: remove a ship from shared stock (cleanup / corrections)."""
    ship = db.get(Ship, ship_id)
    if ship is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ship not found")
    db.delete(ship)
    db.commit()


# --- shipyard build queue ---
@builds_router.get("", response_model=list[ShipBuildOrderOut])
def list_builds(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    orders = (
        db.execute(
            select(ShipBuildOrder)
            .options(
                selectinload(ShipBuildOrder.ship_class),
                selectinload(ShipBuildOrder.shipyard).selectinload(Station.hex_tile),
            )
            .order_by(ShipBuildOrder.created_at)
        )
        .scalars()
        .all()
    )
    names = _names_for(db, {o.queued_by for o in orders})
    return [_order_out(o, names.get(o.queued_by)) for o in orders]


@builds_router.post(
    "", response_model=ShipBuildOrderOut, status_code=status.HTTP_201_CREATED
)
def queue(
    payload: ShipBuildCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_commander),
):
    shipyard = db.execute(
        select(Station)
        .options(selectinload(Station.station_type))
        .where(Station.id == payload.shipyard_id)
    ).scalar_one_or_none()
    if shipyard is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipyard not found")
    ship_class = db.get(ShipClass, payload.ship_class_id)
    if ship_class is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ship class not found")

    try:
        order = queue_build(db, shipyard, ship_class, user)
    except NotAShipyard as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ShipyardFull as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except InsufficientResources as exc:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    db.commit()
    order = db.execute(
        select(ShipBuildOrder)
        .options(
            selectinload(ShipBuildOrder.ship_class),
            selectinload(ShipBuildOrder.shipyard).selectinload(Station.hex_tile),
        )
        .where(ShipBuildOrder.id == order.id)
    ).scalar_one()
    return _order_out(order, user.display_name)


@builds_router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_commander),
):
    """Commander: cancel an in-progress build, freeing the slot. No refund."""
    order = db.get(ShipBuildOrder, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Build order not found")
    db.delete(order)
    db.commit()
