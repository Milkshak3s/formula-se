"""add station construction: station_slots, station_types, stations

Creates the three station tables. The free "Starter Shipyard" type and the
campaign's starting shipyard on the origin sector are materialised idempotently
by the app's run_seeds on boot (services.stations.ensure_starter_station), so
both new and existing campaigns get one — no data seeding needed here.

Revision ID: a4d9e6b2c815
Revises: f3c8d5a2b619
Create Date: 2026-07-05 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a4d9e6b2c815"
down_revision: str | Sequence[str] | None = "f3c8d5a2b619"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATION_KIND = sa.Enum(
    "resource", "shipyard", name="station_kind", native_enum=False
)
_RESOURCE_TYPE = sa.Enum(
    "iron_ingot",
    "nickel_ingot",
    "silicon_wafer",
    "cobalt_ingot",
    name="resource_type",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "station_slots",
        sa.Column("map_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("position_index", sa.Integer(), nullable=False),
        sa.Column("gps_x", sa.Float(), nullable=False),
        sa.Column("gps_y", sa.Float(), nullable=False),
        sa.Column("gps_z", sa.Float(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["map_id"], ["game_maps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_station_slots_map_id"), "station_slots", ["map_id"], unique=False
    )

    op.create_table(
        "station_types",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", _STATION_KIND, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "cost",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("produced_resource", _RESOURCE_TYPE, nullable=True),
        sa.Column("production_amount", sa.Integer(), nullable=False),
        sa.Column("b2_key", sa.String(length=500), nullable=True),
        sa.Column("thumb_b2_key", sa.String(length=500), nullable=True),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_starter", sa.Boolean(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_station_type_name"),
    )

    op.create_table(
        "stations",
        sa.Column("hex_tile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("station_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("built_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("built_on_turn", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["hex_tile_id"], ["hex_tiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["station_type_id"], ["station_types.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["built_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_stations_hex_tile_id"), "stations", ["hex_tile_id"], unique=False
    )
    op.create_index(
        op.f("ix_stations_station_type_id"),
        "stations",
        ["station_type_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stations_station_type_id"), table_name="stations")
    op.drop_index(op.f("ix_stations_hex_tile_id"), table_name="stations")
    op.drop_table("stations")
    op.drop_table("station_types")
    op.drop_index(op.f("ix_station_slots_map_id"), table_name="station_slots")
    op.drop_table("station_slots")
