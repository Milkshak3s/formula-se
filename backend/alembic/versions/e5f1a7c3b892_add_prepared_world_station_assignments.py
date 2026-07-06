"""add prepared_world_station_assignments

Lets a prepared world inject station grids at a map's station slots, mirroring
prepared_world_assignments for ships. Both FKs are SET NULL so a map's station
slots stay editable and a station type stays deletable after an (ephemeral,
TTL-expiring) prepared world has referenced them; snapshot columns preserve the
slot name + coordinates + type name.

Revision ID: e5f1a7c3b892
Revises: d4e9b1c7a256
Create Date: 2026-07-05 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e5f1a7c3b892"
down_revision: str | Sequence[str] | None = "d4e9b1c7a256"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prepared_world_station_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "prepared_world_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("station_slot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("station_slot_name", sa.String(length=120), nullable=False),
        sa.Column("gps_x", sa.Float(), nullable=True),
        sa.Column("gps_y", sa.Float(), nullable=True),
        sa.Column("gps_z", sa.Float(), nullable=True),
        sa.Column("station_type_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("station_type_name", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(
            ["prepared_world_id"], ["prepared_worlds.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["station_slot_id"], ["station_slots.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["station_type_id"], ["station_types.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_prepared_world_station_assignments_prepared_world_id"),
        "prepared_world_station_assignments",
        ["prepared_world_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_prepared_world_station_assignments_prepared_world_id"),
        table_name="prepared_world_station_assignments",
    )
    op.drop_table("prepared_world_station_assignments")
