"""Campaign turn state: read the current turn and advance it.

The turn counter is the anchor future gameplay systems hook into — each advance
is the moment to run per-turn logic (income, upkeep, scheduled events, …). Those
systems don't exist yet; ``run_turn_hooks`` is the single place they'll plug in
so ``advance_turn``'s callers never have to change.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.game import INITIAL_TURN, SINGLETON_ID, GameState, TurnEvent
from app.models.user import User


def get_state(db: Session) -> GameState:
    """Return the singleton game state, creating it (at the initial turn) if absent."""
    state = db.get(GameState, SINGLETON_ID)
    if state is None:
        state = GameState(id=SINGLETON_ID, current_turn=INITIAL_TURN)
        db.add(state)
        try:
            db.commit()
        except IntegrityError:
            # Another worker/replica created it first — reuse that row.
            db.rollback()
            state = db.get(GameState, SINGLETON_ID)
        else:
            db.refresh(state)
    return state


def advance_turn(db: Session, user: User) -> GameState:
    """Increment the campaign turn by one and record who advanced it.

    Locks the singleton row ``FOR UPDATE`` so concurrent "next turn" clicks
    serialize into consecutive turns instead of racing to the same number.
    """
    get_state(db)  # ensure the row exists before we take a row lock on it
    state = db.execute(
        select(GameState).where(GameState.id == SINGLETON_ID).with_for_update()
    ).scalar_one()

    state.current_turn += 1
    state.last_advanced_at = datetime.now(timezone.utc)
    state.last_advanced_by = user.id
    db.add(TurnEvent(turn_number=state.current_turn, advanced_by=user.id))

    run_turn_hooks(db, state)

    db.commit()
    db.refresh(state)
    return state


def run_turn_hooks(db: Session, state: GameState) -> None:
    """Per-turn gameplay systems, run inside ``advance_turn``'s transaction.

    After the turn number is bumped and before commit, so anything a system
    writes lands atomically with the turn change (a failing system rolls the
    whole advance back). Imported lazily to avoid a stations↔turns import cycle.

    Wired systems:
      * resource generation — each resource station credits the treasury.
      * ship construction — every in-progress build advances a turn; finished
        ones complete into shared ship stock at their shipyard's sector.
      * ship movement — every pending move order relocates its ship to the
        destination sector and is cleared.
    """
    from app.services.ships import progress_ship_builds, progress_ship_moves
    from app.services.stations import generate_turn_resources

    generate_turn_resources(db)
    progress_ship_builds(db)
    progress_ship_moves(db)
