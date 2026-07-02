"""Orchestrate preparing a world: fetch map + blueprints, inject, store zip.

Invoked by the background worker for a ``prepared_world`` row. Pure-ish: takes a
DB session and a prepared-world id, does all the I/O, and flips the row's status.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import PreparedWorldStatus
from app.models.ship import Blueprint
from app.models.world import GameMap, PreparedWorld, StartSlot
from app.services.seformat.blueprint import extract_bp_sbc, extract_grids_xml
from app.services.seformat.worldsave import GridPlacement, prepare_world
from app.services.storage import get_storage


def prepared_world_key(pw_id: uuid.UUID) -> str:
    return f"prepared-worlds/{pw_id}.zip"


def process_prepared_world(db: Session, prepared_world_id: str) -> None:
    pw = db.get(PreparedWorld, uuid.UUID(str(prepared_world_id)))
    if pw is None:
        return

    pw.status = PreparedWorldStatus.processing
    pw.error = None
    db.commit()

    try:
        storage = get_storage()
        game_map = db.get(GameMap, pw.map_id)
        if game_map is None:
            raise ValueError("Game map no longer exists")

        world_zip = storage.get(game_map.b2_key)

        placements: list[GridPlacement] = []
        for assignment in pw.assignments:
            start_slot = db.get(StartSlot, assignment.start_slot_id)
            blueprint = db.get(Blueprint, assignment.blueprint_id)
            if start_slot is None or blueprint is None:
                continue
            bp_raw = storage.get(blueprint.b2_key)
            bp_sbc = extract_bp_sbc(bp_raw)
            grids_xml = extract_grids_xml(bp_sbc)
            placements.append(
                GridPlacement(
                    grids_xml=grids_xml,
                    x=start_slot.gps_x,
                    y=start_slot.gps_y,
                    z=start_slot.gps_z,
                )
            )

        result_zip = prepare_world(
            world_zip=world_zip,
            session_name=pw.name,
            placements=placements,
            folder_name=pw.name,
        )

        key = prepared_world_key(pw.id)
        storage.put(key, result_zip, content_type="application/zip")

        pw.b2_key = key
        pw.status = PreparedWorldStatus.ready
        pw.expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.prepared_world_ttl_hours
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 — surface any failure to the user
        db.rollback()
        pw = db.get(PreparedWorld, uuid.UUID(str(prepared_world_id)))
        if pw is not None:
            pw.status = PreparedWorldStatus.failed
            pw.error = str(exc)[:2000]
            db.commit()
        raise
