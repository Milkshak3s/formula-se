from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ResourceType, StationKind


# --- station slots on a game map (admin authoring) ---
class StationSlotIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    position_index: int = 0
    # Either supply gps_string OR explicit coords (mirrors StartSlotIn).
    gps_string: str | None = None
    gps_x: float | None = None
    gps_y: float | None = None
    gps_z: float | None = None


class StationSlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    map_id: uuid.UUID
    name: str
    position_index: int
    gps_x: float
    gps_y: float
    gps_z: float


# --- station types (admin-authored templates) ---
class StationTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: StationKind
    description: str = ""
    # {resource: amount}; only positive amounts are meaningful.
    cost: dict[ResourceType, int] = Field(default_factory=dict)
    produced_resource: ResourceType | None = None
    production_amount: int = Field(default=0, ge=0)
    # Concurrent build slots for shipyards; ignored for resource stations.
    build_slots: int = Field(default=1, ge=1)

    @field_validator("cost")
    @classmethod
    def _non_negative_cost(cls, v: dict[ResourceType, int]) -> dict[ResourceType, int]:
        if any(amount < 0 for amount in v.values()):
            raise ValueError("Cost amounts must be non-negative")
        return v

    @model_validator(mode="after")
    def _resource_station_needs_production(self):
        if self.kind == StationKind.resource:
            if self.produced_resource is None or self.production_amount <= 0:
                raise ValueError(
                    "Resource stations need a produced_resource and a positive "
                    "production_amount"
                )
        return self


class StationTypeUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = None
    cost: dict[ResourceType, int] | None = None
    produced_resource: ResourceType | None = None
    production_amount: int | None = Field(default=None, ge=0)
    build_slots: int | None = Field(default=None, ge=1)


class StationTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    kind: StationKind
    description: str
    cost: dict[ResourceType, int] = Field(default_factory=dict)
    produced_resource: ResourceType | None = None
    production_amount: int
    build_slots: int
    has_blueprint: bool = False
    stats: dict = Field(default_factory=dict)
    is_starter: bool
    created_at: datetime


# --- built stations ---
class StationBuild(BaseModel):
    hex_tile_id: uuid.UUID
    station_type_id: uuid.UUID


class StationOut(BaseModel):
    id: uuid.UUID
    hex_tile_id: uuid.UUID
    q: int
    r: int
    station_type_id: uuid.UUID
    station_type_name: str
    kind: StationKind
    produced_resource: ResourceType | None = None
    production_amount: int
    built_by: uuid.UUID | None = None
    built_by_name: str | None = None
    built_on_turn: int
    created_at: datetime
