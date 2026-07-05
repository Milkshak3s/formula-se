"""The campaign resource treasury.

Resources are a **global**, campaign-wide pool (roles are global in the MVP —
one campaign, no teams), mirroring the singleton turn/sector-map systems. The
treasury is stored as one row per :class:`~app.models.enums.ResourceType`
(a small key/value table) rather than a fixed set of columns, so future
resources append without a schema change.

This iteration only *tracks and displays* balances. The write paths — spending
on ship/station construction and per-turn generation by stations — arrive in
later feature passes; :func:`app.services.resources.adjust_balance` is the
primitive they will build on.
"""
from __future__ import annotations

from sqlalchemy import BigInteger, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import ResourceType

# Every resource starts the campaign at this amount.
STARTING_AMOUNT = 5000


class ResourceBalance(Base):
    __tablename__ = "resource_balances"

    resource: Mapped[ResourceType] = mapped_column(
        Enum(ResourceType, name="resource_type", native_enum=False),
        primary_key=True,
    )
    # BigInteger: balances accumulate over many turns of generation.
    amount: Mapped[int] = mapped_column(
        BigInteger, default=STARTING_AMOUNT, nullable=False
    )
