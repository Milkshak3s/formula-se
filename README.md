# Formula SE

Formula Space Engineers — a management tool for **Space Engineers 1** campaigns:
blueprint intake with rule-based validation, world save management, and
pre-start ship placement. See [PLAN.md](PLAN.md) for the full MVP design.

## What it does

A league organizer (**Game Admin**) defines the rules of the game — **Ship
Classes** with validation requirements and **Game Maps** with designated start
positions. **Engineers** upload ship blueprints (validated on upload against
class rules), and **Commanders** assemble a match: pick a map, assign ships to
start slots, and generate a ready-to-run world save with the ships injected at
their coordinates.

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · lxml |
| Auth | email/password (argon2) · httpOnly cookie sessions in Postgres |
| Data | Postgres (relational + sessions + job queue) |
| Storage | Backblaze B2 (S3 API via boto3), local-filesystem fallback in dev |
| Jobs | Postgres-backed queue (`SELECT … FOR UPDATE SKIP LOCKED`) + worker |
| Frontend | React · Vite · TypeScript · Tailwind · TanStack Query · React Router |
| Deploy | Docker Compose (`api`, `worker`, `postgres`, `caddy`) |

## Quick start (Docker)

```bash
docker compose up --build
```

Then open **http://localhost:8080**. A bootstrap admin is created on first boot
(`admin@formula.se` / `changeme123` by default — override via
`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`). The default registration
invite code is `FORMULA-SE`.

## Local development

**Backend** (needs a Postgres; `DATABASE_URL` defaults to a local one):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # edit as needed
uvicorn app.main:app --reload # API on :8000
python -m app.worker          # background worker (separate terminal)
pytest                        # 19 unit tests
```

Without B2 credentials the app stores artifacts on local disk and serves
downloads through an `/api/files` passthrough, so it runs fully offline.

**Frontend:**

```bash
cd frontend
npm install
npm run dev   # Vite dev server on :5173, proxies /api to :8000
```

## Block data (PCU / weapon detection)

Validation needs a **block-definitions** dataset (PCU + weapon flags) that isn't
in blueprints — it lives in SE's game files. Formula SE ships a small vanilla
seed (`backend/data/block_definitions.json`) so it works out of the box.
To use a full/updated dataset:

```bash
cd backend
python scripts/extract_blockdata.py "<SE install>/Content/Data" -o data/block_definitions.json
```

Admins can also re-upload `CubeBlocks*.sbc` (or a zip of `Content/Data`) from the
Admin screen after an SE patch. Blueprints containing any block absent from the
dataset **hard-fail** validation (this doubles as the mod detector — vanilla
only in the MVP).

## Repo layout

```
backend/
  app/
    api/         routers: auth, users, ship_classes, slots, blueprints,
                 maps, prepared_worlds, blockdata, settings, files
    core/        config, database, security, deps (require_role)
    models/      SQLAlchemy models
    schemas/     Pydantic schemas
    services/    storage (B2/local), blockdata, jobs, worldprep,
                 settings_store, deliverers/, validation/, seformat/
    main.py      FastAPI app          worker.py  job loop + janitor
  data/          block_definitions.json (seed)
  scripts/       extract_blockdata.py
  alembic/       migrations           tests/     unit + fixtures
frontend/
  src/           pages, components, api client, auth, theme
docker-compose.yml
```

## Status

MVP milestones 1–5 are implemented end-to-end and covered by unit tests plus a
full API smoke test (auth → validation → world prep → download). Remaining:
Alembic migration authoring (dev uses `create_all`), design polish (milestone 6),
and a concrete dedicated-server `WorldDeliverer` (deferred behind a flag).
