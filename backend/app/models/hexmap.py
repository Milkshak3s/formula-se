"""The campaign sector map: a hex grid the campaign plays out on.

Like :class:`~app.models.game.GameState`, the map is a **singleton** — one
campaign, one map (roles are global in the MVP). ``HexMap`` holds the map's
shape (its ``radius``); ``HexTile`` is one hex, addressed by axial coordinates
``(q, r)`` (see redblobgames.com/grids/hexagons — pointy-top axial).

This is deliberately the *board*, not the *pieces*. Future features — Commanders
constructing stations on a hex and moving ships between hexes — will add their
own tables keyed on a tile's ``(q, r)`` (or ``id``); the tile is the stable
anchor those systems attach to. None of that is built here.
"""
from __future__ import annotations

from sqlalchemy import Enum, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import HexTerrain
from app.models.mixins import Timestamped, UUIDPk

# The one and only row id for the singleton map table (mirrors GameState).
SINGLETON_ID = 1
# Default map extent: a hexagon of this axial radius (0 = a single centre hex).
DEFAULT_RADIUS = 4
# Guard rails for admin-driven regeneration. Radius 8 is 217 hexes — plenty for
# an MVP campaign while keeping the grid renderable and the payload small.
MIN_RADIUS = 1
MAX_RADIUS = 8


class HexMap(Base):
    __tablename__ = "hex_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=SINGLETON_ID)
    name: Mapped[str] = mapped_column(String(160), default="Campaign Sector", nullable=False)
    # Hexagonal extent in axial rings from the centre. The tile set is derived
    # from this (see services.hexmap.tiles_in_radius) and regenerated on change.
    radius: Mapped[int] = mapped_column(Integer, default=DEFAULT_RADIUS, nullable=False)


class HexTile(UUIDPk, Timestamped, Base):
    __tablename__ = "hex_tiles"
    __table_args__ = (
        # Axial coordinates uniquely identify a hex on the (single) map.
        UniqueConstraint("q", "r", name="uq_hex_tile_qr"),
    )

    # Axial coordinates. Indexed together via the unique constraint above.
    q: Mapped[int] = mapped_column(Integer, nullable=False)
    r: Mapped[int] = mapped_column(Integer, nullable=False)
    terrain: Mapped[HexTerrain] = mapped_column(
        Enum(HexTerrain, name="hex_terrain", native_enum=False),
        default=HexTerrain.deep_space,
        nullable=False,
    )
    # Optional operator/lore label for a notable sector (empty for most hexes).
    name: Mapped[str] = mapped_column(Text, default="", nullable=False)
