"""Auth + authorization FastAPI dependencies."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_agent_token
from app.models.enums import Role
from app.models.server import GameServer
from app.models.user import Session as UserSession
from app.models.user import User


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    session = db.get(UserSession, token)
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")

    now = datetime.now(timezone.utc)
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        db.delete(session)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")

    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def get_optional_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


def get_current_server(
    request: Request, db: Session = Depends(get_db)
) -> GameServer:
    """Authenticate a server agent via an ``Authorization: Bearer <token>`` header.

    Machine auth is deliberately header-based (not the session cookie), so the
    agent needs no browser/cookie/CORS machinery.
    """
    auth = request.headers.get("Authorization", "")
    scheme, _, token = auth.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing agent token")
    server = db.execute(
        select(GameServer).where(GameServer.token_hash == hash_agent_token(token))
    ).scalar_one_or_none()
    if server is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid agent token")
    return server


def require_role(minimum: Role):
    """Dependency factory enforcing the ordered role hierarchy."""

    def _checker(user: User = Depends(get_current_user)) -> User:
        if not user.role.satisfies(minimum):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Requires {minimum.value} role or higher",
            )
        return user

    return _checker


# Convenience aliases used by routers.
require_member = require_role(Role.member)
require_engineer = require_role(Role.engineer)
require_commander = require_role(Role.commander)
require_admin = require_role(Role.admin)
