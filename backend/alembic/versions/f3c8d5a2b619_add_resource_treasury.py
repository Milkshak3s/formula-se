"""add resource_balances: the campaign resource treasury

Row-per-resource treasury, seeded at 5000 each so the campaign has resources
from first migrate. Idempotently re-ensured on boot by run_seeds.

Revision ID: f3c8d5a2b619
Revises: e2b7c4f9a103
Create Date: 2026-07-05 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f3c8d5a2b619"
down_revision: str | Sequence[str] | None = "e2b7c4f9a103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resource_balances",
        sa.Column(
            "resource",
            sa.Enum(
                "iron_ingot",
                "nickel_ingot",
                "silicon_wafer",
                "cobalt_ingot",
                name="resource_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("resource"),
    )
    # Seed the treasury at 5000 of each resource.
    op.execute(
        "INSERT INTO resource_balances (resource, amount) VALUES "
        "('iron_ingot', 5000), "
        "('nickel_ingot', 5000), "
        "('silicon_wafer', 5000), "
        "('cobalt_ingot', 5000)"
    )


def downgrade() -> None:
    op.drop_table("resource_balances")
