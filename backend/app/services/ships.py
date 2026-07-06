"""Ship construction logic: queue a build, progress builds each turn, complete
them into shared stock, plus admin ship grants.

Reuses the treasury spend primitives from :mod:`app.services.stations`
(``normalize_cost`` / ``missing_resources`` and the row-lock pattern) so queuing
a build charges resources exactly like building a station. Queuing is capped by
the shipyard's ``build_slots`` (all in-progress orders advance in parallel — no
waiting queue). Cancelling frees the slot with **no refund**, matching the
no-refund station demolish and "ships in build are lost with their shipyard".
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import StationKind
from app.models.hexmap import HexTile
from app.models.resource import ResourceBalance
from app.models.ship import Ship, ShipBuildOrder, ShipClass, ShipMoveOrder
from app.models.station import Station
from app.models.user import User
from app.services.hexmap import hex_distance
from app.services.stations import (
    InsufficientResources,
    missing_resources,
    normalize_cost,
)
from app.services.turns import get_state


class NotAShipyard(Exception):
    """Raised when a build is queued against a non-shipyard station."""


class ShipyardFull(Exception):
    """Raised when a shipyard has no free build slot for another order."""

    def __init__(self, build_slots: int):
        self.build_slots = build_slots
        super().__init__(
            f"Shipyard is full — all {build_slots} build slots are in use"
        )


class InvalidMove(Exception):
    """Raised when a ship is ordered to the sector it is already in."""


class OutOfRange(Exception):
    """Raised when a move destination is farther than the ship's speed."""

    def __init__(self, distance: int, speed: int):
        self.distance = distance
        self.speed = speed
        super().__init__(
            f"Destination is {distance} sectors away — this ship can only move "
            f"{speed} per turn"
        )


def active_order_count(db: Session, shipyard_id) -> int:
    """How many orders the shipyard currently has in progress."""
    return db.execute(
        select(func.count())
        .select_from(ShipBuildOrder)
        .where(ShipBuildOrder.shipyard_id == shipyard_id)
    ).scalar_one()


def queue_build(
    db: Session, shipyard: Station, ship_class: ShipClass, user: User
) -> ShipBuildOrder:
    """Charge the treasury and queue a ship build on a shipyard. Caller commits.

    Validates the station is a shipyard (:class:`NotAShipyard`) and has a free
    build slot (:class:`ShipyardFull`), then locks the balance rows and spends
    the class's cost (:class:`InsufficientResources` if the campaign can't afford
    it, leaving balances untouched). The order starts at ``build_time`` turns.
    """
    if shipyard.station_type.kind != StationKind.shipyard:
        raise NotAShipyard("Ships can only be built at a shipyard")

    build_slots = shipyard.station_type.build_slots
    if active_order_count(db, shipyard.id) >= build_slots:
        raise ShipyardFull(build_slots)

    cost = normalize_cost(ship_class.cost)

    # Lock every resource row so the check-then-spend is atomic (mirrors
    # build_station — concurrent queues can't both spend the same resources).
    rows = {
        b.resource: b
        for b in db.execute(select(ResourceBalance).with_for_update()).scalars()
    }
    have = {r: rows[r].amount for r in rows}
    short = missing_resources(have, cost)
    if short:
        raise InsufficientResources(short)

    for resource, amount in cost.items():
        rows[resource].amount -= amount

    order = ShipBuildOrder(
        shipyard_id=shipyard.id,
        ship_class_id=ship_class.id,
        turns_remaining=ship_class.build_time,
        queued_by=user.id,
        queued_on_turn=get_state(db).current_turn,
    )
    db.add(order)
    return order


def progress_ship_builds(db: Session) -> int:
    """Advance every in-progress build by one turn; complete the finished ones.

    Called from ``run_turn_hooks`` inside ``advance_turn``'s transaction, so
    completed ships land atomically with the turn bump. Each finished order is
    deleted and turned into a :class:`Ship` at its shipyard's current sector.
    Does **not** commit. Returns the number of ships completed (for logging/tests).
    """
    orders = (
        db.execute(
            select(ShipBuildOrder).options(selectinload(ShipBuildOrder.shipyard))
        )
        .scalars()
        .all()
    )
    completed = 0
    turn = get_state(db).current_turn
    for order in orders:
        order.turns_remaining -= 1
        if order.turns_remaining > 0:
            continue
        # The shipyard is loaded (its FK CASCADE means it still exists here).
        db.add(
            Ship(
                ship_class_id=order.ship_class_id,
                hex_tile_id=order.shipyard.hex_tile_id,
                built_by=order.queued_by,
                built_on_turn=turn,
            )
        )
        db.delete(order)
        completed += 1
    return completed


def set_move_order(
    db: Session, ship: Ship, dest_tile: HexTile, user: User
) -> ShipMoveOrder:
    """Record (or replace) a ship's pending move to ``dest_tile``. Caller commits.

    The destination must differ from the ship's current sector
    (:class:`InvalidMove`) and be within the ship class's ``speed`` in hexes
    (:class:`OutOfRange`). The move is *not* applied here — it resolves on the
    next turn advance via :func:`progress_ship_moves`. Re-issuing overwrites the
    existing order's destination rather than creating a second one.
    """
    if dest_tile.id == ship.hex_tile_id:
        raise InvalidMove("The ship is already in that sector")

    distance = hex_distance(
        ship.hex_tile.q, ship.hex_tile.r, dest_tile.q, dest_tile.r
    )
    speed = ship.ship_class.speed
    if distance > speed:
        raise OutOfRange(distance, speed)

    turn = get_state(db).current_turn
    order = ship.move_order
    if order is None:
        order = ShipMoveOrder(
            ship_id=ship.id,
            dest_tile_id=dest_tile.id,
            issued_by=user.id,
            issued_on_turn=turn,
        )
        db.add(order)
    else:
        order.dest_tile_id = dest_tile.id
        order.issued_by = user.id
        order.issued_on_turn = turn
    return order


def progress_ship_moves(db: Session) -> int:
    """Resolve every pending move: relocate the ship and clear the order.

    Called from ``run_turn_hooks`` inside ``advance_turn``'s transaction, so
    ships arrive atomically with the turn bump. Each order is validated to be in
    range at issue time and the ship can't have moved since, so relocation is a
    straight repoint of ``hex_tile_id``. Does **not** commit. Returns the number
    of ships moved (for logging/tests).
    """
    orders = db.execute(select(ShipMoveOrder).options(selectinload(ShipMoveOrder.ship))).scalars().all()
    moved = 0
    for order in orders:
        order.ship.hex_tile_id = order.dest_tile_id
        db.delete(order)
        moved += 1
    return moved


def add_ship(
    db: Session, ship_class: ShipClass, tile_id, user: User
) -> Ship:
    """Grant a ship into shared stock at a sector (admin manual add). Caller commits."""
    ship = Ship(
        ship_class_id=ship_class.id,
        hex_tile_id=tile_id,
        built_by=user.id,
        built_on_turn=get_state(db).current_turn,
    )
    db.add(ship)
    return ship
