"""Registered SE dedicated servers driven by the polling agent.

A :class:`GameServer` row is a small reconciliation contract between the web app
and the Windows agent that runs alongside a Space Engineers dedicated server:

* ``desired_prepared_world_id`` — what an operator wants running (``None`` means
  "should be stopped"). Set by the "Start"/"Stop" endpoints.
* ``reported_*`` — what the agent last told us it is actually doing.

The agent authenticates with a bearer token; we store only its SHA-256 digest
(the plaintext is shown once at creation/rotation).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import Timestamped, UUIDPk


class GameServer(UUIDPk, Timestamped, Base):
    __tablename__ = "game_servers"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    # Non-secret leading chars of the token, for identification in the UI.
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)

    desired_prepared_world_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepared_worlds.id", ondelete="SET NULL"),
        nullable=True,
    )
    # offline | idle | starting | running | error  (reported by the agent; plain
    # string, mirroring Job.status — no enum type/migration to maintain).
    reported_state: Mapped[str] = mapped_column(
        String(20), default="offline", nullable=False
    )
    reported_prepared_world_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prepared_worlds.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Two FKs point at prepared_worlds, so foreign_keys is required to
    # disambiguate. Both are read-only conveniences.
    desired_prepared_world: Mapped["PreparedWorld | None"] = relationship(  # noqa: F821
        "PreparedWorld", foreign_keys=[desired_prepared_world_id], viewonly=True
    )
    reported_prepared_world: Mapped["PreparedWorld | None"] = relationship(  # noqa: F821
        "PreparedWorld", foreign_keys=[reported_prepared_world_id], viewonly=True
    )
