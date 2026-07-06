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
    requirements: list[RequirementIn] = Field(default_factory=list)

    _validate_cost = field_validator("cost")(_non_negative_cost)


class ShipClassUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = None
    cost: dict[ResourceType, int] | None = None
    build_time: int | None = Field(default=None, ge=1)
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
    created_at: datetime
    requirements: list[RequirementOut] = Field(default_factory=list)


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
