"""Pure-logic coverage for the resource treasury (no DB — the DB-bound seed/read
paths are exercised by the throwaway-Postgres smoke, per project convention)."""
from __future__ import annotations

from app.core.database import Base
from app.models.enums import ResourceType
from app.models.resource import STARTING_AMOUNT, ResourceBalance
from app.schemas.resource import ResourceBalanceOut, ResourceStateOut
from app.services.resources import RESOURCE_TYPES, clamp_amount


def test_table_is_registered_with_metadata():
    # Guards the app.models.__init__ import wiring (Alembic/create_all see it).
    assert ResourceBalance.__tablename__ == "resource_balances"
    assert "resource_balances" in Base.metadata.tables


def test_the_four_resources_are_tracked():
    assert [r.value for r in RESOURCE_TYPES] == [
        "iron_ingot",
        "nickel_ingot",
        "silicon_wafer",
        "cobalt_ingot",
    ]


def test_starting_amount_is_5000():
    assert STARTING_AMOUNT == 5000


def test_clamp_amount_floors_at_zero():
    assert clamp_amount(5000, -200) == 4800
    assert clamp_amount(100, 50) == 150
    # Never negative, no matter how large the debit.
    assert clamp_amount(100, -500) == 0
    assert clamp_amount(0, -1) == 0


def test_resource_balance_out_round_trips():
    b = ResourceBalance(resource=ResourceType.silicon_wafer, amount=1234)
    out = ResourceBalanceOut.model_validate(b)
    assert out.resource == ResourceType.silicon_wafer
    assert out.amount == 1234


def test_resource_state_out_defaults_to_empty():
    assert ResourceStateOut().balances == []
