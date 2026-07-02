"""Ship classes, requirements, blueprint slots, and blueprints."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import BlueprintStatus, RequirementType
from app.models.mixins import Timestamped, UUIDPk


class ShipClass(UUIDPk, Timestamped, Base):
    __tablename__ = "ship_classes"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
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
