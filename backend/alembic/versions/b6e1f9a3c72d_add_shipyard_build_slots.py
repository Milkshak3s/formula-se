"""add build_slots to station_types

Adds the shipyard "build slots" stat: how many ships a shipyard can have under
construction at once. Meaningful for shipyards; defaults to 1 for every existing
row (and for resource stations, where it is ignored).

Revision ID: b6e1f9a3c72d
Revises: a4d9e6b2c815
Create Date: 2026-07-05 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b6e1f9a3c72d"
down_revision: str | Sequence[str] | None = "a4d9e6b2c815"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "station_types",
        sa.Column(
            "build_slots",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    # Drop the server default now that existing rows are backfilled; the app
    # supplies the value on every insert.
    op.alter_column("station_types", "build_slots", server_default=None)


def downgrade() -> None:
    op.drop_column("station_types", "build_slots")
