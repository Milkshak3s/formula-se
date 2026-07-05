"""add game_state + turn_events for the campaign turn system

Revision ID: c9f4a2d81e60
Revises: b7e2a1c9d4f3
Create Date: 2026-07-05 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c9f4a2d81e60"
down_revision: str | Sequence[str] | None = "b7e2a1c9d4f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "game_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("current_turn", sa.Integer(), nullable=False),
        sa.Column("last_advanced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_advanced_by", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["last_advanced_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Seed the singleton row at turn 1 so the app has state from first migrate.
    op.execute("INSERT INTO game_state (id, current_turn) VALUES (1, 1)")

    op.create_table(
        "turn_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("advanced_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["advanced_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_turn_events_turn_number", "turn_events", ["turn_number"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_turn_events_turn_number", table_name="turn_events")
    op.drop_table("turn_events")
    op.drop_table("game_state")
