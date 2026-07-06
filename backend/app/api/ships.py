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
from app.models.ship import Ship, ShipBuildOrder, ShipClass, ShipMoveOrder
from app.models.station import Station
from app.models.user import User
from app.schemas.ship import (
    ShipBuildCreate,
    ShipBuildOrderOut,
    ShipCreate,
    ShipMoveCreate,
    ShipMoveOrderOut,
    ShipOut,
)
from app.services.ships import (
    InsufficientResources,
    InvalidMove,
    NotAShipyard,
    OutOfRange,
    ShipyardFull,
    add_ship,
    queue_build,
    set_move_order,
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


def _move_out(order: ShipMoveOrder, issuer_name: str | None) -> ShipMoveOrderOut:
    return ShipMoveOrderOut(
        id=order.id,
        ship_id=order.ship_id,
        dest_tile_id=order.dest_tile_id,
        dest_q=order.dest_tile.q,
        dest_r=order.dest_tile.r,
        issued_by=order.issued_by,
        issued_by_name=issuer_name,
        issued_on_turn=order.issued_on_turn,
        created_at=order.created_at,
    )


def _ship_out(
    ship: Ship, builder_name: str | None, issuer_name: str | None = None
) -> ShipOut:
    return ShipOut(
        id=ship.id,
        ship_class_id=ship.ship_class_id,
        ship_class_name=ship.ship_class.name,
        speed=ship.ship_class.speed,
        hex_tile_id=ship.hex_tile_id,
        q=ship.hex_tile.q,
        r=ship.hex_tile.r,
        built_by=ship.built_by,
        built_by_name=builder_name,
        built_on_turn=ship.built_on_turn,
        created_at=ship.created_at,
        move_order=(
            _move_out(ship.move_order, issuer_name)
            if ship.move_order is not None
            else None
        ),
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
                selectinload(Ship.ship_class),
                selectinload(Ship.hex_tile),
                selectinload(Ship.move_order).selectinload(ShipMoveOrder.dest_tile),
            )
            .order_by(Ship.created_at)
        )
        .scalars()
        .all()
    )
    ids = {s.built_by for s in ships}
    ids |= {s.move_order.issued_by for s in ships if s.move_order is not None}
    names = _names_for(db, ids)
    return [
        _ship_out(
            s,
            names.get(s.built_by),
            names.get(s.move_order.issued_by) if s.move_order else None,
        )
        for s in ships
    ]


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
        .options(
            selectinload(Ship.ship_class),
            selectinload(Ship.hex_tile),
            selectinload(Ship.move_order),
        )
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


@ships_router.post("/{ship_id}/move", response_model=ShipMoveOrderOut)
def move_ship(
    ship_id: uuid.UUID,
    payload: ShipMoveCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_commander),
):
    """Commander: order a ship to a sector within its speed. Resolves next turn."""
    ship = db.execute(
        select(Ship)
        .options(
            selectinload(Ship.ship_class),
            selectinload(Ship.hex_tile),
            selectinload(Ship.move_order),
        )
        .where(Ship.id == ship_id)
    ).scalar_one_or_none()
    if ship is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ship not found")
    dest = db.get(HexTile, payload.dest_tile_id)
    if dest is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sector not found")

    try:
        order = set_move_order(db, ship, dest, user)
    except (InvalidMove, OutOfRange) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    db.commit()
    order = db.execute(
        select(ShipMoveOrder)
        .options(selectinload(ShipMoveOrder.dest_tile))
        .where(ShipMoveOrder.id == order.id)
    ).scalar_one()
    return _move_out(order, user.display_name)


@ships_router.delete("/{ship_id}/move", status_code=status.HTTP_204_NO_CONTENT)
def cancel_move(
    ship_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_commander),
):
    """Commander: call off a ship's pending move (before the next turn)."""
    order = db.execute(
        select(ShipMoveOrder).where(ShipMoveOrder.ship_id == ship_id)
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending move for this ship")
    db.delete(order)
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
