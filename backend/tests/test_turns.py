"""Pure-logic coverage for the turn system (no DB — see the smoke test for the
DB-bound advance path, which is verified against a throwaway Postgres)."""
from __future__ import annotations

from app.core.database import Base
from app.models.game import INITIAL_TURN, SINGLETON_ID, GameState, TurnEvent
from app.schemas.turn import TurnEventOut, TurnStateOut


def test_singleton_and_initial_turn_constants():
    assert SINGLETON_ID == 1
    # Campaigns open on turn 1; the first "next turn" advances to 2.
    assert INITIAL_TURN == 1


def test_tables_are_registered_with_metadata():
    # Guards the app.models.__init__ import wiring (Alembic/create_all see them).
    tables = set(Base.metadata.tables)
    assert GameState.__tablename__ == "game_state"
    assert TurnEvent.__tablename__ == "turn_events"
    assert {"game_state", "turn_events"} <= tables


def test_turn_state_out_defaults_to_empty_history():
    state = TurnStateOut(current_turn=1)
    assert state.current_turn == 1
    assert state.history == []
    assert state.last_advanced_by_name is None


def test_turn_event_out_round_trips():
    import uuid
    from datetime import datetime, timezone

    eid = uuid.uuid4()
    uid = uuid.uuid4()
    now = datetime(2026, 7, 5, tzinfo=timezone.utc)
    ev = TurnEventOut(
        id=eid, turn_number=3, advanced_by=uid, advanced_by_name="Ada", created_at=now
    )
    assert ev.turn_number == 3
    assert ev.advanced_by_name == "Ada"


def test_run_turn_hooks_wires_resource_generation():
    # run_turn_hooks now drives per-turn resource generation from stations
    # (the DB-bound behaviour is verified in the throwaway-Postgres smoke).
    from app.services import turns as turns_mod

    assert callable(turns_mod.run_turn_hooks)
