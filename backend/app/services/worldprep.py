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
from app.models.station import StationSlot, StationType
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
            blueprint = db.get(Blueprint, assignment.blueprint_id)
            if blueprint is None:
                continue
            # Prefer the coordinate snapshot captured at assignment time; fall
            # back to the live start slot if the snapshot is absent (older rows).
            x, y, z = assignment.gps_x, assignment.gps_y, assignment.gps_z
            if x is None or y is None or z is None:
                start_slot = (
                    db.get(StartSlot, assignment.start_slot_id)
                    if assignment.start_slot_id
                    else None
                )
                if start_slot is None:
                    continue
                x, y, z = start_slot.gps_x, start_slot.gps_y, start_slot.gps_z
            bp_raw = storage.get(blueprint.b2_key)
            bp_sbc = extract_bp_sbc(bp_raw)
            grids_xml = extract_grids_xml(bp_sbc)
            placements.append(GridPlacement(grids_xml=grids_xml, x=x, y=y, z=z))

        # Inject the chosen station grids the same way, at their station-slot GPS.
        for station_assignment in pw.station_assignments:
            if station_assignment.station_type_id is None:
                continue
            station_type = db.get(StationType, station_assignment.station_type_id)
            if station_type is None or not station_type.b2_key:
                continue
            x, y, z = (
                station_assignment.gps_x,
                station_assignment.gps_y,
                station_assignment.gps_z,
            )
            if x is None or y is None or z is None:
                station_slot = (
                    db.get(StationSlot, station_assignment.station_slot_id)
                    if station_assignment.station_slot_id
                    else None
                )
                if station_slot is None:
                    continue
                x, y, z = station_slot.gps_x, station_slot.gps_y, station_slot.gps_z
            st_raw = storage.get(station_type.b2_key)
            st_sbc = extract_bp_sbc(st_raw)
            grids_xml = extract_grids_xml(st_sbc)
            placements.append(GridPlacement(grids_xml=grids_xml, x=x, y=y, z=z))

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
