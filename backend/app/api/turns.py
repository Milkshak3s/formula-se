"""Campaign turn endpoints: read the current turn, and (Commander+) advance it."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_commander
from app.models.game import GameState, TurnEvent
from app.models.user import User
from app.schemas.turn import TurnEventOut, TurnStateOut
from app.services.turns import advance_turn, get_state

router = APIRouter(prefix="/api/turns", tags=["turns"])

# How many recent advances to surface alongside the current turn.
HISTORY_LIMIT = 10


def _names_for(db: Session, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(User.id, User.display_name).where(User.id.in_(user_ids))
    ).all()
    return {uid: name for uid, name in rows}


def _state_out(db: Session, state: GameState) -> TurnStateOut:
    events = (
        db.execute(
            select(TurnEvent)
            .order_by(TurnEvent.turn_number.desc())
            .limit(HISTORY_LIMIT)
        )
        .scalars()
        .all()
    )
    ids = {e.advanced_by for e in events if e.advanced_by}
    if state.last_advanced_by:
        ids.add(state.last_advanced_by)
    names = _names_for(db, ids)
    return TurnStateOut(
        current_turn=state.current_turn,
        last_advanced_at=state.last_advanced_at,
        last_advanced_by=state.last_advanced_by,
        last_advanced_by_name=names.get(state.last_advanced_by),
        history=[
            TurnEventOut(
                id=e.id,
                turn_number=e.turn_number,
                advanced_by=e.advanced_by,
                advanced_by_name=names.get(e.advanced_by),
                created_at=e.created_at,
            )
            for e in events
        ],
    )


@router.get("", response_model=TurnStateOut)
def get_turn(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return _state_out(db, get_state(db))


@router.post("/advance", response_model=TurnStateOut)
def advance(db: Session = Depends(get_db), user: User = Depends(require_commander)):
    state = advance_turn(db, user)
    return _state_out(db, state)
