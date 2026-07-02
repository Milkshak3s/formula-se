from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BlueprintStatus, RequirementType


class RequirementIn(BaseModel):
    rule_type: RequirementType
    params: dict[str, Any] = Field(default_factory=dict)


class RequirementOut(RequirementIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class ShipClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    requirements: list[RequirementIn] = Field(default_factory=list)


class ShipClassUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = None
    requirements: list[RequirementIn] | None = None


class ShipClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str
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
