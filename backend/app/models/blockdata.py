"""Block definitions dataset (PCU + weapon flags) parsed from CubeBlocks*.sbc."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BlockDefinition(Base):
    __tablename__ = "block_definitions"
    __table_args__ = (
        UniqueConstraint("type_id", "subtype_id", name="uq_block_type_subtype"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    subtype_id: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    display_name: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    pcu: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_weapon: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    grid_size: Mapped[str] = mapped_column(String(20), default="", nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="seed", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
