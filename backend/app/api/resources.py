"""Campaign resource endpoints: read the shared treasury.

Read-only for now — the write paths (construction spend, per-turn station
generation) arrive in later feature passes. Any signed-in user can view the
campaign's balances.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.resource import ResourceBalanceOut, ResourceStateOut
from app.services.resources import get_balances

router = APIRouter(prefix="/api/resources", tags=["resources"])


@router.get("", response_model=ResourceStateOut)
def get_resources(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return ResourceStateOut(
        balances=[ResourceBalanceOut.model_validate(b) for b in get_balances(db)]
    )
