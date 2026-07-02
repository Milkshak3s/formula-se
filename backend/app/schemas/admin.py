from __future__ import annotations

from pydantic import BaseModel


class BlockDataStats(BaseModel):
    count: int
    updated_at: str | None
    sources: dict[str, int]


class BlockDataRefreshResult(BaseModel):
    parsed: int
    upserted: int
    source: str


class SettingsOut(BaseModel):
    invite_code: str
    server_push_enabled: bool


class SettingsUpdate(BaseModel):
    invite_code: str | None = None
    server_push_enabled: bool | None = None
