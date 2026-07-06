"""add ship construction: ship_build_orders and ships

Creates the two tables behind ship construction:

* ``ship_build_orders`` — a ship under construction in a shipyard's build slot.
  CASCADE on ``shipyard_id`` so destroying the shipyard (or regenerating the
  sector map) loses everything it had in build; RESTRICT on ``ship_class_id`` so
  a class with active builds can't be deleted.
* ``ships`` — a completed ship in the campaign's shared stock, located on a
  sector (CASCADE with the tile; RESTRICT on its class).

No data seeding — completed ships accrue from play, and admins grant them.

Revision ID: d4e9b1c7a256
Revises: c7a3f5d1e208
Create Date: 2026-07-05 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4e9b1c7a256"
down_revision: str | Sequence[str] | None = "c7a3f5d1e208"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ship_build_orders",
        sa.Column("shipyard_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ship_class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("turns_remaining", sa.Integer(), nullable=False),
        sa.Column("queued_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("queued_on_turn", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["shipyard_id"], ["stations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["ship_class_id"], ["ship_classes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["queued_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ship_build_orders_shipyard_id"),
        "ship_build_orders",
        ["shipyard_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ship_build_orders_ship_class_id"),
        "ship_build_orders",
        ["ship_class_id"],
        unique=False,
    )

    op.create_table(
        "ships",
        sa.Column("ship_class_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hex_tile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("built_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("built_on_turn", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["ship_class_id"], ["ship_classes.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["hex_tile_id"], ["hex_tiles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["built_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ships_ship_class_id"), "ships", ["ship_class_id"], unique=False
    )
    op.create_index(
        op.f("ix_ships_hex_tile_id"), "ships", ["hex_tile_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ships_hex_tile_id"), table_name="ships")
    op.drop_index(op.f("ix_ships_ship_class_id"), table_name="ships")
    op.drop_table("ships")
    op.drop_index(
        op.f("ix_ship_build_orders_ship_class_id"), table_name="ship_build_orders"
    )
    op.drop_index(
        op.f("ix_ship_build_orders_shipyard_id"), table_name="ship_build_orders"
    )
    op.drop_table("ship_build_orders")
