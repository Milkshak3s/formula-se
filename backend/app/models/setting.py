"""Simple key/value application settings (invite code, feature flags)."""
from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

INVITE_CODE_KEY = "invite_code"
SERVER_PUSH_ENABLED_KEY = "server_push_enabled"


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
