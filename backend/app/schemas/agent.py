from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class AgentPollIn(BaseModel):
    """What the agent reports on each poll."""

    state: str = Field(default="idle", max_length=20)
    # The prepared world the agent believes it is currently running (if any).
    prepared_world_id: uuid.UUID | None = None
    error: str | None = None
    agent_version: str | None = None


class DesiredWorld(BaseModel):
    id: uuid.UUID
    name: str
    download_url: str


class AgentDesired(BaseModel):
    action: str  # "run" | "stop"
    prepared_world: DesiredWorld | None = None


class AgentPollOut(BaseModel):
    """Desired state the agent should converge on."""

    server_id: uuid.UUID
    desired: AgentDesired
    poll_interval_seconds: int
