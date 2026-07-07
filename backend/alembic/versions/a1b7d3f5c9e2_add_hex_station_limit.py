"""add per-hex station limit

Adds ``hex_tiles.station_limit`` — the max stations a Commander may build on a
sector (admin-configurable per hex; default 1, 0 = locked). Enforced in
``services.stations.build_station``; seeded/injected stations bypass it.
Backfilled to 1 for existing tiles.

Revision ID: a1b7d3f5c9e2
Revises: f9a3c1e7b2d4
Create Date: 2026-07-06 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "a1b7d3f5c9e2"
down_revision: str | Sequence[str] | None = "f9a3c1e7b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Backfill existing tiles to 1 via a server default, then drop it so the
    # app-level default (1) is the single source of truth going forward.
    op.add_column(
        "hex_tiles",
        sa.Column("station_limit", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("hex_tiles", "station_limit", server_default=None)


def downgrade() -> None:
    op.drop_column("hex_tiles", "station_limit")
