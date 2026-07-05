"""Station construction logic: cost/affordability, building, per-turn generation,
and the seeded free starter shipyard.

Pure cost helpers (:func:`normalize_cost`, :func:`missing_resources`) are DB-free
and unit tested. The DB paths (build, generation, seed) are covered by the
throwaway-Postgres smoke.
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import ResourceType, StationKind
from app.models.hexmap import HexTile
from app.models.resource import ResourceBalance
from app.models.station import STARTER_SHIPYARD_TYPE_ID, Station, StationType
from app.models.user import User
from app.services.resources import ensure_balances
from app.services.turns import get_state

STARTER_SHIPYARD_NAME = "Starter Shipyard"


class InsufficientResources(Exception):
    """Raised when the treasury can't cover a station's build cost."""

    def __init__(self, missing: dict[ResourceType, int]):
        self.missing = missing
        detail = ", ".join(f"{r.value}: {n} short" for r, n in missing.items())
        super().__init__(f"Insufficient resources ({detail})")


def normalize_cost(cost: dict) -> dict[ResourceType, int]:
    """Coerce a raw cost mapping to ``{ResourceType: positive int}``.

    Drops zero/negative entries; raises ``ValueError`` on unknown resource keys.
    """
    out: dict[ResourceType, int] = {}
    for key, value in cost.items():
        resource = key if isinstance(key, ResourceType) else ResourceType(key)
        amount = int(value)
        if amount > 0:
            out[resource] = amount
    return out


def missing_resources(
    balances: dict[ResourceType, int], cost: dict[ResourceType, int]
) -> dict[ResourceType, int]:
    """Return, per resource, how much the balances fall short of the cost."""
    short: dict[ResourceType, int] = {}
    for resource, amount in cost.items():
        have = balances.get(resource, 0)
        if have < amount:
            short[resource] = amount - have
    return short


def build_station(
    db: Session, tile: HexTile, station_type: StationType, user: User
) -> Station:
    """Charge the treasury for a station type and place it on a sector. Caller commits.

    Locks the affected balance rows ``FOR UPDATE`` so concurrent builds can't
    both spend the same resources, and raises :class:`InsufficientResources` if
    the campaign can't afford it (leaving balances untouched).
    """
    ensure_balances(db)
    cost = normalize_cost(station_type.cost)

    # Lock every resource row so the check-then-spend is atomic.
    rows = {
        b.resource: b
        for b in db.execute(
            select(ResourceBalance).with_for_update()
        ).scalars()
    }
    have = {r: rows[r].amount for r in rows}
    short = missing_resources(have, cost)
    if short:
        raise InsufficientResources(short)

    for resource, amount in cost.items():
        rows[resource].amount -= amount

    station = Station(
        hex_tile_id=tile.id,
        station_type_id=station_type.id,
        built_by=user.id,
        built_on_turn=get_state(db).current_turn,
    )
    db.add(station)
    return station


def generate_turn_resources(db: Session) -> dict[ResourceType, int]:
    """Credit the treasury with every resource station's output. Caller commits.

    Called from ``run_turn_hooks`` inside ``advance_turn``'s transaction, so the
    generated resources land atomically with the turn bump. Does **not** commit.
    Returns the per-resource totals generated (for logging/tests).
    """
    stations = (
        db.execute(select(Station).options(selectinload(Station.station_type)))
        .scalars()
        .all()
    )
    totals: dict[ResourceType, int] = {}
    for station in stations:
        st = station.station_type
        if (
            st.kind == StationKind.resource
            and st.produced_resource is not None
            and st.production_amount > 0
        ):
            totals[st.produced_resource] = (
                totals.get(st.produced_resource, 0) + st.production_amount
            )
    if not totals:
        return {}

    ensure_balances(db)
    for resource, amount in totals.items():
        row = db.execute(
            select(ResourceBalance)
            .where(ResourceBalance.resource == resource)
            .with_for_update()
        ).scalar_one()
        row.amount += amount
    return totals


def _get_or_create_starter_type(db: Session) -> StationType:
    st = db.get(StationType, STARTER_SHIPYARD_TYPE_ID)
    if st is None:
        st = StationType(
            id=STARTER_SHIPYARD_TYPE_ID,
            name=STARTER_SHIPYARD_NAME,
            kind=StationKind.shipyard,
            description="The campaign's starting shipyard.",
            cost={},
            production_amount=0,
            is_starter=True,
        )
        db.add(st)
    return st


def ensure_starter_station(db: Session) -> Station | None:
    """Seed the free starter shipyard on the origin sector once per campaign.

    Idempotent: ensures the starter *type* exists, then places one starter
    shipyard on the origin hex (0, 0) only when no stations exist yet — so new
    campaigns and existing ones (on first boot after this deploys) each get
    exactly one free shipyard, without duplicating it on later boots. Commits.
    """
    starter = _get_or_create_starter_type(db)
    db.flush()

    any_station = db.execute(select(Station.id).limit(1)).first()
    if any_station is not None:
        db.commit()
        return None

    origin = db.execute(
        select(HexTile).where(HexTile.q == 0, HexTile.r == 0)
    ).scalar_one_or_none()
    if origin is None:
        db.commit()
        return None

    station = Station(
        hex_tile_id=origin.id,
        station_type_id=starter.id,
        built_by=None,
        built_on_turn=get_state(db).current_turn,
    )
    db.add(station)
    db.commit()
    db.refresh(station)
    return station
