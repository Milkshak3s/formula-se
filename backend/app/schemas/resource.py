from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ResourceType


class ResourceBalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    resource: ResourceType
    amount: int


class ResourceStateOut(BaseModel):
    # Canonical resource order; every tracked resource is always present.
    balances: list[ResourceBalanceOut] = Field(default_factory=list)
