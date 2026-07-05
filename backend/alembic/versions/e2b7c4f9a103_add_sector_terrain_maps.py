"""add sector_terrain_maps: terrain type -> GameMap association

One map per sector terrain type (terrain is the PK); many terrains may share a
map. A sector resolves its map via its terrain. Cascade-deletes with the
referenced GameMap so removing a map simply clears the association.

Revision ID: e2b7c4f9a103
Revises: d1a6f3b52c74
Create Date: 2026-07-05 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e2b7c4f9a103"
down_revision: str | Sequence[str] | None = "d1a6f3b52c74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sector_terrain_maps",
        sa.Column(
            "terrain",
            sa.Enum(
                "deep_space",
                "asteroid_field",
                "nebula",
                "ice_field",
                "planet",
                "star_system",
                name="hex_terrain",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("game_map_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["game_map_id"], ["game_maps.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("terrain"),
    )


def downgrade() -> None:
    op.drop_table("sector_terrain_maps")
