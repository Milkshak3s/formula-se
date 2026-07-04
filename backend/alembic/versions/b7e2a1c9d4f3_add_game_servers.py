"""add game_servers for the server-start agent

Revision ID: b7e2a1c9d4f3
Revises: a832351bb4bd
Create Date: 2026-07-04 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b7e2a1c9d4f3"
down_revision: str | Sequence[str] | None = "a832351bb4bd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "game_servers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column(
            "desired_prepared_world_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("reported_state", sa.String(length=20), nullable=False),
        sa.Column(
            "reported_prepared_world_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["desired_prepared_world_id"], ["prepared_worlds.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["reported_prepared_world_id"], ["prepared_worlds.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_game_servers_token_hash", "game_servers", ["token_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_game_servers_token_hash", table_name="game_servers")
    op.drop_table("game_servers")
