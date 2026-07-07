"""Pure-logic coverage for station construction (no DB — the build/generate/seed
DB paths are exercised by the throwaway-Postgres smoke, per project convention)."""
from __future__ import annotations

import uuid

import pytest

from app.core.database import Base
from app.models.enums import ResourceType, StationKind
from app.models.station import (
    STARTER_SHIPYARD_TYPE_ID,
    Station,
    StationSlot,
    StationType,
)
from app.schemas.hexmap import HexTileUpdate
from app.schemas.station import StationTypeCreate
from app.services.stations import (
    InsufficientResources,
    StationLimitReached,
    missing_resources,
    normalize_cost,
)


def test_tables_are_registered_with_metadata():
    tables = set(Base.metadata.tables)
    assert {"station_slots", "station_types", "stations"} <= tables
    assert StationSlot.__tablename__ == "station_slots"
    assert StationType.__tablename__ == "station_types"
    assert Station.__tablename__ == "stations"


def test_two_station_kinds():
    assert {k.value for k in StationKind} == {"resource", "shipyard"}


def test_starter_type_id_is_deterministic():
    # Same value the migration/seed rely on across processes.
    assert STARTER_SHIPYARD_TYPE_ID == uuid.uuid5(
        uuid.NAMESPACE_DNS, "formula-se.starter-shipyard"
    )


def test_station_type_restrict_ondelete_protects_built_stations():
    fk = next(
        fk
        for fk in Station.__table__.foreign_keys
        if fk.column.table.name == "station_types"
    )
    assert fk.ondelete == "RESTRICT"


def test_station_tile_cascades():
    fk = next(
        fk
        for fk in Station.__table__.foreign_keys
        if fk.column.table.name == "hex_tiles"
    )
    assert fk.ondelete == "CASCADE"


def test_normalize_cost_drops_nonpositive_and_maps_enums():
    cost = normalize_cost({"iron_ingot": 500, "nickel_ingot": 0, "silicon_wafer": 200})
    assert cost == {ResourceType.iron_ingot: 500, ResourceType.silicon_wafer: 200}


def test_normalize_cost_rejects_unknown_resource():
    with pytest.raises(ValueError):
        normalize_cost({"unobtanium": 10})


def test_missing_resources_reports_shortfalls():
    have = {ResourceType.iron_ingot: 100, ResourceType.silicon_wafer: 50}
    cost = {ResourceType.iron_ingot: 250, ResourceType.silicon_wafer: 50}
    short = missing_resources(have, cost)
    # 150 short on iron; silicon exactly covered.
    assert short == {ResourceType.iron_ingot: 150}


def test_missing_resources_empty_when_affordable():
    have = {ResourceType.iron_ingot: 1000}
    assert missing_resources(have, {ResourceType.iron_ingot: 1000}) == {}


def test_insufficient_resources_message():
    exc = InsufficientResources({ResourceType.cobalt_ingot: 42})
    assert "cobalt_ingot" in str(exc)


def test_resource_station_type_requires_production():
    # A resource station with no production is rejected at the schema layer.
    with pytest.raises(ValueError):
        StationTypeCreate(name="Bad Mine", kind=StationKind.resource)
    # Shipyards need no production.
    yard = StationTypeCreate(name="Yard", kind=StationKind.shipyard)
    assert yard.production_amount == 0
    # A well-formed resource station validates.
    mine = StationTypeCreate(
        name="Iron Mine",
        kind=StationKind.resource,
        produced_resource=ResourceType.iron_ingot,
        production_amount=250,
        cost={ResourceType.silicon_wafer: 300},
    )
    assert mine.produced_resource == ResourceType.iron_ingot
    assert mine.production_amount == 250


def test_shipyard_build_slots_default_and_validation():
    # Defaults to a single build slot.
    yard = StationTypeCreate(name="Yard", kind=StationKind.shipyard)
    assert yard.build_slots == 1
    # A shipyard may declare more concurrent slots.
    big = StationTypeCreate(name="Big Yard", kind=StationKind.shipyard, build_slots=4)
    assert big.build_slots == 4
    # Zero/negative slots are rejected at the schema layer.
    with pytest.raises(ValueError):
        StationTypeCreate(name="No Slots", kind=StationKind.shipyard, build_slots=0)


def test_station_type_create_rejects_negative_cost():
    with pytest.raises(ValueError):
        StationTypeCreate(
            name="Freebie",
            kind=StationKind.shipyard,
            cost={ResourceType.iron_ingot: -5},
        )


# --- per-hex station limit ---
def test_hex_tile_has_station_limit_column():
    from app.models.hexmap import HexTile

    assert "station_limit" in HexTile.__table__.c


def test_station_limit_reached_reports_limit():
    exc = StationLimitReached(1)
    assert exc.limit == 1
    assert "1" in str(exc) and "station" in str(exc)
    # Pluralization is handled for readable messages.
    assert "stations" in str(StationLimitReached(3))
    assert "stations" not in str(StationLimitReached(1))


def test_hex_tile_update_accepts_station_limit():
    assert HexTileUpdate(station_limit=0).station_limit == 0
    assert HexTileUpdate(station_limit=5).station_limit == 5
    # Negative limits are rejected at the schema layer.
    with pytest.raises(ValueError):
        HexTileUpdate(station_limit=-1)
