"""add ship movement: ship_classes.speed and ship_move_orders

Ships can now be ordered between sectors. Movement is turn-based:

* ``ship_classes.speed`` — how many sectors a ship of the class may travel per
  turn (a move order's destination must be within this many hexes). Backfilled
  to 1 for existing classes.
* ``ship_move_orders`` — a Commander's pending intent to move a ship. Unique on
  ``ship_id`` (at most one pending move per ship). Both FKs CASCADE: scrapping
  the ship, or a sector-map regenerate (tiles → ships), drops the order too.

No data seeding beyond the ``speed`` backfill.

Revision ID: f9a3c1e7b2d4
Revises: e5f1a7c3b892
Create Date: 2026-07-06 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f9a3c1e7b2d4"
down_revision: str | Sequence[str] | None = "e5f1a7c3b892"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Backfill existing classes to speed 1 via a server default, then drop it so
    # the app-level default (1) is the single source of truth going forward.
    op.add_column(
        "ship_classes",
        sa.Column("speed", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("ship_classes", "speed", server_default=None)

    op.create_table(
        "ship_move_orders",
        sa.Column("ship_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dest_tile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issued_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("issued_on_turn", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["ship_id"], ["ships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["dest_tile_id"], ["hex_tiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ship_move_orders_ship_id"),
        "ship_move_orders",
        ["ship_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_ship_move_orders_dest_tile_id"),
        "ship_move_orders",
        ["dest_tile_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_ship_move_orders_dest_tile_id"), table_name="ship_move_orders"
    )
    op.drop_index(
        op.f("ix_ship_move_orders_ship_id"), table_name="ship_move_orders"
    )
    op.drop_table("ship_move_orders")
    op.drop_column("ship_classes", "speed")
