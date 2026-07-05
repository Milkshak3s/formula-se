"""Station construction: map station-slots, station types, and built stations.

Three pieces:

* :class:`StationSlot` — an admin-placed GPS position on a :class:`GameMap`
  world-save where a station grid will be injected before the world loads on an
  SE server (the injection itself is a later world-prep pass; here we just author
  the slots).
* :class:`StationType` — an admin-authored template a player picks when building:
  its :class:`~app.models.enums.StationKind` (resource vs shipyard), its resource
  ``cost``, the resource + amount a resource station generates per turn, and an
  optional uploaded blueprint (parsed/stored like a ship blueprint).
* :class:`Station` — a constructed station a Commander placed on a sector
  (:class:`~app.models.hexmap.HexTile`), referencing the type it was built from.

Future gates (build only in owned sectors / where you have ships) and the
slot↔station injection wiring are intentionally *not* built here.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ResourceType, StationKind
from app.models.mixins import Timestamped, UUIDPk

# Deterministic id for the seeded free "Starter Shipyard" type, so the seed and
# any migration agree on the same row without coordinating a random value.
STARTER_SHIPYARD_TYPE_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "formula-se.starter-shipyard")


class StationSlot(UUIDPk, Timestamped, Base):
    __tablename__ = "station_slots"

    map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("game_maps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    position_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gps_x: Mapped[float] = mapped_column(Float, nullable=False)
    gps_y: Mapped[float] = mapped_column(Float, nullable=False)
    gps_z: Mapped[float] = mapped_column(Float, nullable=False)

    map = relationship("GameMap", back_populates="station_slots")


class StationType(UUIDPk, Timestamped, Base):
    __tablename__ = "station_types"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    kind: Mapped[StationKind] = mapped_column(
        Enum(StationKind, name="station_kind", native_enum=False), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # Build cost as {resource_value: amount}; only positive entries are stored.
    cost: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    # Per-turn generation (resource stations only; null/0 for shipyards).
    produced_resource: Mapped[ResourceType | None] = mapped_column(
        Enum(ResourceType, name="resource_type", native_enum=False), nullable=True
    )
    production_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Optional blueprint for the station grid (parsed/stored like ship blueprints).
    b2_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    thumb_b2_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    # Marks the seeded free shipyard so it can be protected from deletion.
    is_starter: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    @property
    def has_blueprint(self) -> bool:
        return bool(self.b2_key)


class Station(UUIDPk, Timestamped, Base):
    __tablename__ = "stations"

    # The sector this station sits in. CASCADE: regenerating the map (which
    # replaces its tiles) clears built stations; the starter is re-seeded.
    hex_tile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hex_tiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # RESTRICT: a type with built stations can't be deleted out from under them.
    station_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("station_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    built_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    built_on_turn: Mapped[int] = mapped_column(Integer, nullable=False)

    station_type: Mapped[StationType] = relationship()
    hex_tile = relationship("HexTile")
