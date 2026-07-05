"""Campaign resource-treasury logic: seed, read, and the adjust primitive.

The treasury is a fixed set of rows (one per :class:`ResourceType`), seeded at
``STARTING_AMOUNT``. :func:`ensure_balances` is idempotent so it can run on every
boot. :func:`adjust_balance` is the single mutation primitive future systems
(construction spend, per-turn station generation) will call; it clamps at zero so
a balance can never go negative.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.enums import ResourceType
from app.models.resource import STARTING_AMOUNT, ResourceBalance

# The canonical resource order for display and seeding.
RESOURCE_TYPES: tuple[ResourceType, ...] = tuple(ResourceType)


def clamp_amount(current: int, delta: int) -> int:
    """Apply ``delta`` to ``current``, floored at zero (never negative)."""
    return max(0, current + delta)


def ensure_balances(db: Session) -> int:
    """Create any missing resource rows at the starting amount. Idempotent.

    Safe to call on every startup (``run_seeds``). Returns the number of rows
    created (0 once the treasury exists).
    """
    existing = set(
        db.execute(select(ResourceBalance.resource)).scalars().all()
    )
    created = 0
    for resource in RESOURCE_TYPES:
        if resource in existing:
            continue
        db.add(ResourceBalance(resource=resource, amount=STARTING_AMOUNT))
        created += 1
    if created:
        try:
            db.commit()
        except IntegrityError:
            # Another replica seeded concurrently — reuse the existing rows.
            db.rollback()
            return 0
    return created


def get_balances(db: Session) -> list[ResourceBalance]:
    """Return every resource balance in canonical order, seeding if absent."""
    ensure_balances(db)
    rows = {
        b.resource: b
        for b in db.execute(select(ResourceBalance)).scalars().all()
    }
    return [rows[r] for r in RESOURCE_TYPES if r in rows]


def adjust_balance(db: Session, resource: ResourceType, delta: int) -> ResourceBalance:
    """Add ``delta`` (may be negative) to a resource, clamped at zero. Caller commits.

    The future spend/generation primitive. Locks the row ``FOR UPDATE`` so
    concurrent adjustments serialize instead of racing.
    """
    ensure_balances(db)
    row = db.execute(
        select(ResourceBalance)
        .where(ResourceBalance.resource == resource)
        .with_for_update()
    ).scalar_one()
    row.amount = clamp_amount(row.amount, delta)
    return row
