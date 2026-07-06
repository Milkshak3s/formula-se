"""add cost and build_time to ship_classes

Adds admin-configurable build economics to ship classes: ``cost`` (a
``{resource: amount}`` JSONB map, mirroring ``station_types.cost``) and
``build_time`` (turns a shipyard needs to build one ship of the class).
Existing rows backfill to an empty cost and a 1-turn build time.

Revision ID: c7a3f5d1e208
Revises: b6e1f9a3c72d
Create Date: 2026-07-05 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "c7a3f5d1e208"
down_revision: str | Sequence[str] | None = "b6e1f9a3c72d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ship_classes",
        sa.Column(
            "cost",
            JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "ship_classes",
        sa.Column(
            "build_time",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    # Drop the server defaults now that existing rows are backfilled; the app
    # supplies both values on every insert.
    op.alter_column("ship_classes", "cost", server_default=None)
    op.alter_column("ship_classes", "build_time", server_default=None)


def downgrade() -> None:
    op.drop_column("ship_classes", "build_time")
    op.drop_column("ship_classes", "cost")
