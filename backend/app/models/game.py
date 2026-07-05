"""Global campaign game state: the turn counter and its advance history.

The turn counter is global (roles are global in the MVP — one campaign, no
teams). A single-row ``game_state`` table makes that singleton invariant
explicit; ``SINGLETON_ID`` is the only primary key that ever exists. ``turn_events``
is the append-only audit trail of every advance — who moved the campaign forward
and when — and the natural anchor for per-turn gameplay systems added later.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import Timestamped, UUIDPk

# The one and only row id for the singleton game-state table.
SINGLETON_ID = 1
# Campaigns start on turn 1 (the first turn), so "next turn" lands on 2.
INITIAL_TURN = 1


class GameState(Base):
    __tablename__ = "game_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=SINGLETON_ID)
    current_turn: Mapped[int] = mapped_column(
        Integer, default=INITIAL_TURN, nullable=False
    )
    last_advanced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_advanced_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class TurnEvent(UUIDPk, Timestamped, Base):
    __tablename__ = "turn_events"

    # The turn number the campaign entered as a result of this advance.
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    advanced_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
