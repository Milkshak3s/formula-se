from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import HexTerrain
from app.models.hexmap import MAX_RADIUS, MIN_RADIUS


class HexTileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    q: int
    r: int
    terrain: HexTerrain
    name: str
    # Max stations a Commander may build here (admin-set; default 1, 0 = locked).
    station_limit: int


class TerrainMapOut(BaseModel):
    terrain: HexTerrain
    game_map_id: uuid.UUID
    game_map_name: str


class HexMapOut(BaseModel):
    id: int
    name: str
    radius: int
    tiles: list[HexTileOut] = Field(default_factory=list)
    # Terrain→map assignments; a sector resolves its map via its terrain.
    terrain_maps: list[TerrainMapOut] = Field(default_factory=list)


class TerrainMapUpdate(BaseModel):
    # None clears the assignment for this terrain.
    game_map_id: uuid.UUID | None = None


class HexMapRegenerate(BaseModel):
    # Bounded here too so a bad radius is a 422, not a silently clamped grid.
    radius: int = Field(ge=MIN_RADIUS, le=MAX_RADIUS)
    name: str | None = Field(default=None, max_length=160)


class HexTileUpdate(BaseModel):
    terrain: HexTerrain | None = None
    name: str | None = Field(default=None, max_length=200)
    # 0 locks the sector to new builds; no upper cap.
    station_limit: int | None = Field(default=None, ge=0)
