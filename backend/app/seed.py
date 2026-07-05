"""Idempotent bootstrap: seed block definitions and a bootstrap admin.

Run on API/worker startup. Safe to call repeatedly.
"""
from __future__ import annotations

import os

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.blockdata import BlockDefinition
from app.models.enums import Role
from app.models.user import User
from app.services.blockdata import load_seed_json, upsert_block_defs
from app.services.hexmap import ensure_tiles
from app.services.resources import ensure_balances
from app.services.stations import ensure_starter_station
from app.services.turns import get_state


def seed_block_definitions(db: Session) -> int:
    existing = db.execute(select(func.count()).select_from(BlockDefinition)).scalar_one()
    if existing:
        return 0
    path = settings.block_definitions_seed
    if not os.path.isabs(path):
        # Resolve relative to the backend/ directory.
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, path)
    if not os.path.exists(path):
        return 0
    defs = load_seed_json(path)
    return upsert_block_defs(db, defs, source="seed")


def seed_bootstrap_admin(db: Session) -> User | None:
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return None
    email = settings.bootstrap_admin_email.lower().strip()
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        return existing
    user = User(
        email=email,
        display_name=settings.bootstrap_admin_name,
        password_hash=hash_password(settings.bootstrap_admin_password),
        role=Role.admin,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Another replica created the admin first (unique email). Not an error.
        db.rollback()
        return db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    db.refresh(user)
    return user


def run_seeds(db: Session) -> None:
    seed_block_definitions(db)
    seed_bootstrap_admin(db)
    # Ensure the singleton game-state row (turn 1) exists from first boot.
    get_state(db)
    # Ensure the singleton sector map exists and its default grid is populated.
    ensure_tiles(db)
    # Ensure the campaign resource treasury exists (5000 of each to start).
    ensure_balances(db)
    # Ensure the campaign's free starter shipyard exists on the origin sector.
    ensure_starter_station(db)
