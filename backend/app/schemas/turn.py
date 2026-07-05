from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class TurnEventOut(BaseModel):
    id: uuid.UUID
    turn_number: int
    advanced_by: uuid.UUID | None = None
    advanced_by_name: str | None = None
    created_at: datetime


class TurnStateOut(BaseModel):
    current_turn: int
    last_advanced_at: datetime | None = None
    last_advanced_by: uuid.UUID | None = None
    last_advanced_by_name: str | None = None
    # Most-recent advances first; empty until the first "next turn".
    history: list[TurnEventOut] = []
