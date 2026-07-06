from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import BlueprintStatus, RequirementType, ResourceType


class RequirementIn(BaseModel):
    rule_type: RequirementType
    params: dict[str, Any] = Field(default_factory=dict)


class RequirementOut(RequirementIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


def _non_negative_cost(v: dict[ResourceType, int]) -> dict[ResourceType, int]:
    if any(amount < 0 for amount in v.values()):
        raise ValueError("Cost amounts must be non-negative")
    return v


class ShipClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    # {resource: amount}; only positive amounts are meaningful.
    cost: dict[ResourceType, int] = Field(default_factory=dict)
    # Turns to build one ship of this class.
    build_time: int = Field(default=1, ge=1)
    # Sectors a ship of this class can travel per turn.
    speed: int = Field(default=1, ge=1)
    requirements: list[RequirementIn] = Field(default_factory=list)

    _validate_cost = field_validator("cost")(_non_negative_cost)


class ShipClassUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = None
    cost: dict[ResourceType, int] | None = None
    build_time: int | None = Field(default=None, ge=1)
    speed: int | None = Field(default=None, ge=1)
    requirements: list[RequirementIn] | None = None

    @field_validator("cost")
    @classmethod
    def _check_cost(cls, v: dict[ResourceType, int] | None) -> dict[ResourceType, int] | None:
        return v if v is None else _non_negative_cost(v)


class ShipClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str
    cost: dict[ResourceType, int] = Field(default_factory=dict)
    build_time: int
    speed: int
    created_at: datetime
    requirements: list[RequirementOut] = Field(default_factory=list)


# --- ship construction: build orders and completed stock ---
class ShipBuildCreate(BaseModel):
    shipyard_id: uuid.UUID
    ship_class_id: uuid.UUID


class ShipBuildOrderOut(BaseModel):
    id: uuid.UUID
    shipyard_id: uuid.UUID
    q: int
    r: int
    ship_class_id: uuid.UUID
    ship_class_name: str
    turns_remaining: int
    build_time: int
    queued_by: uuid.UUID | None = None
    queued_by_name: str | None = None
    queued_on_turn: int
    created_at: datetime


class ShipCreate(BaseModel):
    """Admin manual ship grant into shared stock."""

    ship_class_id: uuid.UUID
    hex_tile_id: uuid.UUID


class ShipMoveCreate(BaseModel):
    """Commander move intent: send a ship to a sector within its speed."""

    dest_tile_id: uuid.UUID


class ShipMoveOrderOut(BaseModel):
    id: uuid.UUID
    ship_id: uuid.UUID
    dest_tile_id: uuid.UUID
    dest_q: int
    dest_r: int
    issued_by: uuid.UUID | None = None
    issued_by_name: str | None = None
    issued_on_turn: int
    created_at: datetime


class ShipOut(BaseModel):
    id: uuid.UUID
    ship_class_id: uuid.UUID
    ship_class_name: str
    # The class's per-turn move range, so the UI can offer in-range destinations.
    speed: int
    hex_tile_id: uuid.UUID
    q: int
    r: int
    built_by: uuid.UUID | None = None
    built_by_name: str | None = None
    built_on_turn: int
    created_at: datetime
    # The ship's pending move, if any (resolves on the next turn advance).
    move_order: ShipMoveOrderOut | None = None


class BlueprintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slot_id: uuid.UUID
    uploader_id: uuid.UUID | None
    name: str
    stats: dict[str, Any]
    status: BlueprintStatus
    created_at: datetime
    has_thumbnail: bool = False


class BlueprintHistoryOut(BaseModel):
    """A slot's upload history row — makes overwrites visible (PLAN §3.3)."""

    id: uuid.UUID
    name: str
    status: BlueprintStatus
    stats: dict[str, Any]
    uploader_name: str | None
    has_thumbnail: bool
    created_at: datetime


class SlotCreate(BaseModel):
    ship_class_id: uuid.UUID
    name: str = Field(min_length=1, max_length=120)


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    ship_class_id: uuid.UUID
    name: str
    created_at: datetime
    ship_class_name: str | None = None
    active_blueprint: BlueprintOut | None = None

    @property
    def status(self) -> str:
        return "filled" if self.active_blueprint else "empty"
