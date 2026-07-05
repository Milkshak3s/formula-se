"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    agent,
    auth,
    blockdata,
    blueprints,
    files,
    maps,
    prepared_worlds,
    servers,
    settings as settings_router,
    ship_classes,
    slots,
    turns,
    users,
)
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.seed import run_seeds


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In dev, create tables for zero-setup convenience; in prod Alembic owns the
    # schema (AUTO_CREATE_TABLES=false). Seeds always run (idempotent).
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run_seeds(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth.router,
    users.router,
    ship_classes.router,
    slots.router,
    blueprints.router,
    maps.router,
    prepared_worlds.router,
    turns.router,
    servers.router,
    agent.router,
    blockdata.router,
    settings_router.router,
    files.router,
):
    app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}
