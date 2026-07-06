"""Game maps, start slots, prepared worlds, and assignments."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import PreparedWorldStatus
from app.models.mixins import Timestamped, UUIDPk


class GameMap(UUIDPk, Timestamped, Base):
    __tablename__ = "game_maps"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    b2_key: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    start_slots: Mapped[list["StartSlot"]] = relationship(
        back_populates="map",
        cascade="all, delete-orphan",
        order_by="StartSlot.position_index",
    )
    # Station-grid injection points (added in the station-construction feature).
    station_slots: Mapped[list["StationSlot"]] = relationship(
        back_populates="map",
        cascade="all, delete-orphan",
        order_by="StationSlot.position_index",
    )


class StartSlot(UUIDPk, Timestamped, Base):
    __tablename__ = "start_slots"

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
    # Reserved for post-MVP orientation support — nullable from day one.
    orient_forward_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    orient_forward_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    orient_forward_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    orient_up_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    orient_up_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    orient_up_z: Mapped[float | None] = mapped_column(Float, nullable=True)

    map: Mapped[GameMap] = relationship(back_populates="start_slots")
    supported_classes: Mapped[list["StartSlotClass"]] = relationship(
        back_populates="start_slot", cascade="all, delete-orphan"
    )


class StartSlotClass(Base):
    __tablename__ = "start_slot_classes"
    __table_args__ = (
        UniqueConstraint("start_slot_id", "ship_class_id", name="uq_startslot_class"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    start_slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("start_slots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ship_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ship_classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    start_slot: Mapped[StartSlot] = relationship(back_populates="supported_classes")


class PreparedWorld(UUIDPk, Timestamped, Base):
    __tablename__ = "prepared_worlds"

    map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("game_maps.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    b2_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[PreparedWorldStatus] = mapped_column(
        Enum(PreparedWorldStatus, name="prepared_world_status", native_enum=False),
        default=PreparedWorldStatus.queued,
        nullable=False,
        index=True,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    map: Mapped[GameMap] = relationship()
    assignments: Mapped[list["PreparedWorldAssignment"]] = relationship(
        back_populates="prepared_world", cascade="all, delete-orphan"
    )
    station_assignments: Mapped[list["PreparedWorldStationAssignment"]] = relationship(
        back_populates="prepared_world", cascade="all, delete-orphan"
    )


class PreparedWorldAssignment(Base):
    __tablename__ = "prepared_world_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    prepared_world_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepared_worlds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SET NULL (not RESTRICT) so a map's start slots stay editable after a world
    # has used them; the snapshot columns below preserve the history.
    start_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("start_slots.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Snapshot of the start slot at assignment time (survives slot edits/deletes).
    start_slot_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    gps_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Pins the exact blueprint version, surviving later slot overwrites.
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blueprints.id", ondelete="RESTRICT"),
        nullable=False,
    )

    prepared_world: Mapped[PreparedWorld] = relationship(back_populates="assignments")


class PreparedWorldStationAssignment(Base):
    """A station grid chosen for one of a map's station slots in a prepared world.

    Mirrors :class:`PreparedWorldAssignment` but for stations: a
    :class:`~app.models.station.StationType` (which carries an uploaded grid
    blueprint) is injected at the station slot's GPS. Snapshots the slot's name +
    coordinates so later map edits don't rewrite history. Both FKs are SET NULL:
    a station slot stays editable and a station type stays deletable after an
    (ephemeral, TTL-expiring) prepared world has referenced them — at prep time a
    null type is simply skipped.
    """

    __tablename__ = "prepared_world_station_assignments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    prepared_world_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepared_worlds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    station_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("station_slots.id", ondelete="SET NULL"),
        nullable=True,
    )
    station_slot_name: Mapped[str] = mapped_column(
        String(120), default="", nullable=False
    )
    gps_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_z: Mapped[float | None] = mapped_column(Float, nullable=True)
    station_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("station_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    station_type_name: Mapped[str] = mapped_column(
        String(120), default="", nullable=False
    )

    prepared_world: Mapped[PreparedWorld] = relationship(
        back_populates="station_assignments"
    )
