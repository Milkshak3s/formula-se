"""Ship classes, requirements, blueprint slots, and blueprints."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import BlueprintStatus, RequirementType
from app.models.mixins import Timestamped, UUIDPk


class ShipClass(UUIDPk, Timestamped, Base):
    __tablename__ = "ship_classes"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # Admin-configurable build cost as {resource_value: amount}; only positive
    # entries are stored (mirrors StationType.cost).
    cost: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    # Turns a shipyard needs to build one ship of this class.
    build_time: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="ship_class",
        cascade="all, delete-orphan",
        order_by="Requirement.created_at",
    )
    slots: Mapped[list["BlueprintSlot"]] = relationship(
        back_populates="ship_class", cascade="all, delete-orphan"
    )


class ShipBuildOrder(UUIDPk, Timestamped, Base):
    """A ship under construction, occupying one of a shipyard's build slots.

    Slots are tied to the specific shipyard (``Station``): the FK CASCADEs, so if
    the shipyard is demolished or the sector map is regenerated the in-progress
    order is lost (the ship never finishes). ``turns_remaining`` starts at the
    class's ``build_time`` and is decremented each turn; when it hits zero the
    order is deleted and a :class:`Ship` is created at the shipyard's sector.

    A shipyard may host at most ``StationType.build_slots`` orders at once, all
    progressing in parallel — there is no waiting queue beyond the slots.
    """

    __tablename__ = "ship_build_orders"

    # The shipyard station building this ship. CASCADE: destroying the shipyard
    # (or regenerating the map) loses everything it had in build.
    shipyard_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # RESTRICT: a class with active builds can't be deleted out from under them.
    ship_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ship_classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    turns_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    queued_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    queued_on_turn: Mapped[int] = mapped_column(Integer, nullable=False)

    ship_class: Mapped[ShipClass] = relationship()
    shipyard = relationship("Station")


class Ship(UUIDPk, Timestamped, Base):
    """A completed ship in the campaign's shared stock, sitting on a sector.

    Ships are campaign-wide (not individually owned), mirroring the shared
    treasury. A ship's ``hex_tile`` is its location on the sector map — it starts
    at the shipyard that built it (or wherever an admin places a manually granted
    ship). Movement and other map interactions are a later pass. CASCADE with the
    tile: regenerating the sector map (a full board reset) clears ship stock too.
    """

    __tablename__ = "ships"

    # RESTRICT: a class with ships in stock can't be deleted out from under them.
    ship_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ship_classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # The sector this ship is located in. CASCADE with the tile (map regenerate).
    hex_tile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hex_tiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Who caused this ship to exist: the commander who queued its build, the admin
    # who granted it, or null for a campaign gift. Purely informational.
    built_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    built_on_turn: Mapped[int] = mapped_column(Integer, nullable=False)

    ship_class: Mapped[ShipClass] = relationship()
    hex_tile = relationship("HexTile")


class Requirement(UUIDPk, Timestamped, Base):
    __tablename__ = "requirements"

    ship_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ship_classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_type: Mapped[RequirementType] = mapped_column(
        Enum(RequirementType, name="requirement_type", native_enum=False),
        nullable=False,
    )
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    ship_class: Mapped[ShipClass] = relationship(back_populates="requirements")


class BlueprintSlot(UUIDPk, Timestamped, Base):
    __tablename__ = "blueprint_slots"

    ship_class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ship_classes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    ship_class: Mapped[ShipClass] = relationship(back_populates="slots")
    blueprints: Mapped[list["Blueprint"]] = relationship(
        back_populates="slot", cascade="all, delete-orphan"
    )

    @property
    def active_blueprint(self) -> "Blueprint | None":
        for bp in self.blueprints:
            if bp.status == BlueprintStatus.active:
                return bp
        return None


class Blueprint(UUIDPk, Timestamped, Base):
    __tablename__ = "blueprints"
    __table_args__ = (
        # Enforce at most one ACTIVE blueprint per slot at the DB level;
        # replaced/cleared rows are kept as audit history (PLAN §5).
        Index(
            "uq_blueprint_active_per_slot",
            "slot_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("blueprint_slots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploader_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    b2_key: Mapped[str] = mapped_column(String(500), nullable=False)
    thumb_b2_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[BlueprintStatus] = mapped_column(
        Enum(BlueprintStatus, name="blueprint_status", native_enum=False),
        default=BlueprintStatus.active,
        nullable=False,
    )

    slot: Mapped[BlueprintSlot] = relationship(back_populates="blueprints")

    @property
    def has_thumbnail(self) -> bool:
        return bool(self.thumb_b2_key)
