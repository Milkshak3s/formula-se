"""add hex_map + hex_tiles for the campaign sector map

Creates the singleton map table (seeded here so state exists from first migrate)
and the hex-tile table. The tile set itself is materialised idempotently by the
app's ``run_seeds`` on boot (services.hexmap.ensure_tiles), keeping this
migration free of the generation logic.

Revision ID: d1a6f3b52c74
Revises: c9f4a2d81e60
Create Date: 2026-07-05 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d1a6f3b52c74"
down_revision: str | Sequence[str] | None = "c9f4a2d81e60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hex_map",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("radius", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # Seed the singleton map (radius 4) so state exists from first migrate.
    op.execute(
        "INSERT INTO hex_map (id, name, radius) VALUES (1, 'Campaign Sector', 4)"
    )

    op.create_table(
        "hex_tiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("q", sa.Integer(), nullable=False),
        sa.Column("r", sa.Integer(), nullable=False),
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
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("q", "r", name="uq_hex_tile_qr"),
    )


def downgrade() -> None:
    op.drop_table("hex_tiles")
    op.drop_table("hex_map")
