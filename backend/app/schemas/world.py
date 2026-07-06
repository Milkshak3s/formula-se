from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PreparedWorldStatus
from app.schemas.station import StationSlotIn, StationSlotOut


class StartSlotIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    position_index: int = 0
    # Either supply gps_string OR explicit coords.
    gps_string: str | None = None
    gps_x: float | None = None
    gps_y: float | None = None
    gps_z: float | None = None
    ship_class_ids: list[uuid.UUID] = Field(default_factory=list)


class StartSlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    map_id: uuid.UUID
    name: str
    position_index: int
    gps_x: float
    gps_y: float
    gps_z: float
    ship_class_ids: list[uuid.UUID] = Field(default_factory=list)


class MapCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""


class MapUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    description: str | None = None
    start_slots: list[StartSlotIn] | None = None
    station_slots: list[StationSlotIn] | None = None


class MapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str
    created_at: datetime
    start_slots: list[StartSlotOut] = Field(default_factory=list)
    station_slots: list[StationSlotOut] = Field(default_factory=list)


class AssignmentIn(BaseModel):
    start_slot_id: uuid.UUID
    slot_id: uuid.UUID | None = None  # None → leave start slot empty


class StationAssignmentIn(BaseModel):
    station_slot_id: uuid.UUID
    station_type_id: uuid.UUID | None = None  # None → leave station slot empty


class PreparedWorldCreate(BaseModel):
    map_id: uuid.UUID
    name: str = Field(min_length=1, max_length=160)
    assignments: list[AssignmentIn] = Field(default_factory=list)
    station_assignments: list[StationAssignmentIn] = Field(default_factory=list)


class PreparedWorldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    map_id: uuid.UUID
    name: str
    status: PreparedWorldStatus
    error: str | None
    expires_at: datetime | None
    created_at: datetime
