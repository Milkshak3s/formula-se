"""Read/write app settings (invite code, feature flags) with config defaults."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.models.setting import (
    INVITE_CODE_KEY,
    SERVER_PUSH_ENABLED_KEY,
    AppSetting,
)


def get_setting(db: Session, key: str, default: str | None = None) -> str | None:
    row = db.get(AppSetting, key)
    return row.value if row else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        row = AppSetting(key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()


def get_invite_code(db: Session) -> str:
    return get_setting(db, INVITE_CODE_KEY, app_settings.default_invite_code) or ""


def get_server_push_enabled(db: Session) -> bool:
    raw = get_setting(db, SERVER_PUSH_ENABLED_KEY)
    if raw is None:
        return app_settings.server_push_enabled
    return raw.lower() in ("1", "true", "yes", "on")
