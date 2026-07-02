from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.setting import INVITE_CODE_KEY, SERVER_PUSH_ENABLED_KEY
from app.models.user import User
from app.schemas.admin import PublicSettings, SettingsOut, SettingsUpdate
from app.services.settings_store import (
    get_invite_code,
    get_server_push_enabled,
    set_setting,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/public", response_model=PublicSettings)
def public_settings(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Non-sensitive settings any authenticated user may read (e.g. to decide
    whether to show the 'Push to server' action)."""
    return PublicSettings(server_push_enabled=get_server_push_enabled(db))


@router.get("", response_model=SettingsOut)
def get_settings_(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return SettingsOut(
        invite_code=get_invite_code(db),
        server_push_enabled=get_server_push_enabled(db),
    )


@router.patch("", response_model=SettingsOut)
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if payload.invite_code is not None:
        set_setting(db, INVITE_CODE_KEY, payload.invite_code.strip())
    if payload.server_push_enabled is not None:
        set_setting(
            db, SERVER_PUSH_ENABLED_KEY, "true" if payload.server_push_enabled else "false"
        )
    return SettingsOut(
        invite_code=get_invite_code(db),
        server_push_enabled=get_server_push_enabled(db),
    )
