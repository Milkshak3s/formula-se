"""Agent-facing endpoints (bearer-token auth) for the SE server host."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_server
from app.models.enums import PreparedWorldStatus
from app.models.server import GameServer
from app.models.world import PreparedWorld
from app.schemas.agent import AgentDesired, AgentPollIn, AgentPollOut, DesiredWorld
from app.services.servers import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    absolutize_url,
    normalize_reported_state,
)
from app.services.storage import get_storage

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/poll", response_model=AgentPollOut)
def poll(
    payload: AgentPollIn,
    request: Request,
    db: Session = Depends(get_db),
    server: GameServer = Depends(get_current_server),
):
    """Single heartbeat: record what the agent reported, return desired state.

    The agent posts its current state each cycle and receives the world it should
    be running (``run``) or an instruction to shut down (``stop``). This is a
    reconcile loop, not a queue — the agent re-converges on every poll, so a
    restart is self-healing.
    """
    # 1. Record the report (also the liveness heartbeat).
    server.reported_state = normalize_reported_state(payload.state)
    server.reported_prepared_world_id = payload.prepared_world_id
    server.last_error = payload.error
    server.last_seen_at = datetime.now(timezone.utc)

    # 2. Resolve desired state. A desired world only yields a "run" order once it
    #    is actually downloadable; if it isn't ready (e.g. it expired and its
    #    b2_key was cleared), fall back to "stop".
    desired = AgentDesired(action="stop", prepared_world=None)
    if server.desired_prepared_world_id is not None:
        pw = db.get(PreparedWorld, server.desired_prepared_world_id)
        if pw is not None and pw.status == PreparedWorldStatus.ready and pw.b2_key:
            url = get_storage().presigned_url(pw.b2_key, download_name=f"{pw.name}.zip")
            desired = AgentDesired(
                action="run",
                prepared_world=DesiredWorld(
                    id=pw.id,
                    name=pw.name,
                    download_url=absolutize_url(url, str(request.base_url)),
                ),
            )

    db.commit()

    return AgentPollOut(
        server_id=server.id,
        desired=desired,
        poll_interval_seconds=DEFAULT_POLL_INTERVAL_SECONDS,
    )
