"""Pure-logic coverage for ship construction (no DB — the queue/progress/grant
DB paths are exercised by the throwaway-Postgres smoke, per project convention)."""
from __future__ import annotations

import uuid

import pytest

from app.core.database import Base
from app.models.ship import Ship, ShipBuildOrder
from app.schemas.ship import ShipBuildCreate, ShipCreate
from app.services.ships import NotAShipyard, ShipyardFull


def test_tables_are_registered_with_metadata():
    tables = set(Base.metadata.tables)
    assert {"ship_build_orders", "ships"} <= tables
    assert ShipBuildOrder.__tablename__ == "ship_build_orders"
    assert Ship.__tablename__ == "ships"


def _fk(model, target_table):
    return next(
        fk for fk in model.__table__.foreign_keys if fk.column.table.name == target_table
    )


def test_build_order_cascades_with_its_shipyard():
    # Ships in build are lost when their shipyard disappears (feature requirement).
    assert _fk(ShipBuildOrder, "stations").ondelete == "CASCADE"


def test_build_order_restricts_its_class():
    # A class with active builds can't be deleted out from under them.
    assert _fk(ShipBuildOrder, "ship_classes").ondelete == "RESTRICT"


def test_completed_ship_cascades_with_its_tile_and_restricts_its_class():
    assert _fk(Ship, "hex_tiles").ondelete == "CASCADE"
    assert _fk(Ship, "ship_classes").ondelete == "RESTRICT"


def test_shipyard_full_message_reports_slot_count():
    exc = ShipyardFull(3)
    assert exc.build_slots == 3
    assert "3" in str(exc)


def test_not_a_shipyard_is_an_exception():
    with pytest.raises(NotAShipyard):
        raise NotAShipyard("nope")


def test_build_create_requires_shipyard_and_class():
    payload = ShipBuildCreate(shipyard_id=uuid.uuid4(), ship_class_id=uuid.uuid4())
    assert payload.shipyard_id and payload.ship_class_id
    with pytest.raises(ValueError):
        ShipBuildCreate(ship_class_id=uuid.uuid4())  # missing shipyard_id


def test_ship_create_requires_class_and_tile():
    payload = ShipCreate(ship_class_id=uuid.uuid4(), hex_tile_id=uuid.uuid4())
    assert payload.ship_class_id and payload.hex_tile_id
    with pytest.raises(ValueError):
        ShipCreate(ship_class_id=uuid.uuid4())  # missing hex_tile_id


def test_run_turn_hooks_wires_ship_progress():
    # Ship-build progression is imported lazily inside run_turn_hooks; make sure
    # the service entrypoint it calls exists and is callable.
    from app.services.ships import progress_ship_builds

    assert callable(progress_ship_builds)
