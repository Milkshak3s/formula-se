"""Operator/UI endpoints for registering and controlling SE dedicated servers."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin, require_commander
from app.core.security import generate_agent_token, hash_agent_token
from app.models.enums import PreparedWorldStatus
from app.models.server import GameServer
from app.models.user import User
from app.models.world import PreparedWorld
from app.schemas.server import (
    ServerCreatedOut,
    ServerOut,
    ServerRegisterIn,
    ServerStartIn,
)
from app.services.servers import is_online
from app.services.settings_store import get_server_push_enabled

router = APIRouter(prefix="/api/servers", tags=["servers"])


def _out(server: GameServer) -> ServerOut:
    return ServerOut(
        id=server.id,
        name=server.name,
        token_prefix=server.token_prefix,
        reported_state=server.reported_state,
        online=is_online(server.last_seen_at),
        desired_prepared_world_id=server.desired_prepared_world_id,
        reported_prepared_world_id=server.reported_prepared_world_id,
        last_error=server.last_error,
        last_seen_at=server.last_seen_at,
        created_at=server.created_at,
    )


def _issue_token(server: GameServer) -> str:
    """Generate a fresh token, store its digest + display prefix, return plaintext."""
    token = generate_agent_token()
    server.token_hash = hash_agent_token(token)
    server.token_prefix = token[:12]
    return token


def _require_push_enabled(db: Session) -> None:
    if not get_server_push_enabled(db):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Server control is disabled (enable it in Settings).",
        )


def _get_server(db: Session, server_id: uuid.UUID) -> GameServer:
    server = db.get(GameServer, server_id)
    if server is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Server not found")
    return server


@router.get("", response_model=list[ServerOut])
def list_servers(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    servers = (
        db.execute(select(GameServer).order_by(GameServer.created_at.desc()))
        .scalars()
        .all()
    )
    return [_out(s) for s in servers]


@router.post("", response_model=ServerCreatedOut, status_code=status.HTTP_201_CREATED)
def register_server(
    payload: ServerRegisterIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    server = GameServer(
        name=payload.name.strip(), created_by=user.id, token_hash="", token_prefix=""
    )
    token = _issue_token(server)
    db.add(server)
    db.commit()
    db.refresh(server)
    return ServerCreatedOut(**_out(server).model_dump(), token=token)


@router.post("/{server_id}/rotate-token", response_model=ServerCreatedOut)
def rotate_token(
    server_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    server = _get_server(db, server_id)
    token = _issue_token(server)
    db.commit()
    db.refresh(server)
    return ServerCreatedOut(**_out(server).model_dump(), token=token)


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_server(
    server_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    server = _get_server(db, server_id)
    db.delete(server)
    db.commit()


@router.post("/{server_id}/start", response_model=ServerOut)
def start_server(
    server_id: uuid.UUID,
    payload: ServerStartIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_commander),
):
    _require_push_enabled(db)
    server = _get_server(db, server_id)
    pw = db.get(PreparedWorld, payload.prepared_world_id)
    if pw is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prepared world not found")
    if pw.status != PreparedWorldStatus.ready or not pw.b2_key:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Prepared world is not ready ({pw.status.value})",
        )
    server.desired_prepared_world_id = pw.id
    db.commit()
    db.refresh(server)
    return _out(server)


@router.post("/{server_id}/stop", response_model=ServerOut)
def stop_server(
    server_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_commander),
):
    _require_push_enabled(db)
    server = _get_server(db, server_id)
    server.desired_prepared_world_id = None
    db.commit()
    db.refresh(server)
    return _out(server)
