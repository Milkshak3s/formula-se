from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.ship import Requirement, ShipClass
from app.models.user import User
from app.schemas.ship import ShipClassCreate, ShipClassOut, ShipClassUpdate

router = APIRouter(prefix="/api/ship-classes", tags=["ship-classes"])


def _load(db: Session, class_id: uuid.UUID) -> ShipClass:
    obj = db.execute(
        select(ShipClass)
        .options(selectinload(ShipClass.requirements))
        .where(ShipClass.id == class_id)
    ).scalar_one_or_none()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ship class not found")
    return obj


@router.get("", response_model=list[ShipClassOut])
def list_classes(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return (
        db.execute(
            select(ShipClass)
            .options(selectinload(ShipClass.requirements))
            .order_by(ShipClass.name)
        )
        .scalars()
        .all()
    )


@router.post("", response_model=ShipClassOut, status_code=status.HTTP_201_CREATED)
def create_class(
    payload: ShipClassCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    existing = db.execute(
        select(ShipClass).where(ShipClass.name == payload.name)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ship class name already exists")

    obj = ShipClass(
        name=payload.name,
        description=payload.description,
        cost={r.value: a for r, a in payload.cost.items() if a > 0},
        build_time=payload.build_time,
        speed=payload.speed,
        created_by=admin.id,
    )
    for req in payload.requirements:
        obj.requirements.append(
            Requirement(rule_type=req.rule_type, params=req.params)
        )
    db.add(obj)
    db.commit()
    return _load(db, obj.id)


@router.patch("/{class_id}", response_model=ShipClassOut)
def update_class(
    class_id: uuid.UUID,
    payload: ShipClassUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    obj = _load(db, class_id)
    if payload.name is not None:
        obj.name = payload.name
    if payload.description is not None:
        obj.description = payload.description
    if payload.cost is not None:
        obj.cost = {r.value: a for r, a in payload.cost.items() if a > 0}
    if payload.build_time is not None:
        obj.build_time = payload.build_time
    if payload.speed is not None:
        obj.speed = payload.speed
    if payload.requirements is not None:
        # Replace the whole requirement set.
        obj.requirements.clear()
        db.flush()
        for req in payload.requirements:
            obj.requirements.append(
                Requirement(rule_type=req.rule_type, params=req.params)
            )
    db.commit()
    return _load(db, class_id)


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_class(
    class_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    obj = _load(db, class_id)
    db.delete(obj)
    db.commit()
