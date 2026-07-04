from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ServerOut(BaseModel):
    id: uuid.UUID
    name: str
    token_prefix: str
    reported_state: str
    online: bool = False
    desired_prepared_world_id: uuid.UUID | None = None
    reported_prepared_world_id: uuid.UUID | None = None
    last_error: str | None = None
    last_seen_at: datetime | None = None
    created_at: datetime


class ServerCreatedOut(ServerOut):
    # The plaintext bearer token — returned exactly once (on register / rotate).
    token: str


class ServerRegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ServerStartIn(BaseModel):
    prepared_world_id: uuid.UUID
