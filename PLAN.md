# Formula SE — MVP Plan

> A management tool for Space Engineers 1 campaigns: blueprint intake with
> rule-based validation, world save management, and pre-start ship placement.
>
> **Status: decision-complete for MVP** (2026-07-02). This doc is the living
> plan; see §8 for the decisions log. Next step: milestone 1 spike (§7).

## 1. Product summary

Formula SE lets a league/campaign organizer (Game Admin) define the "rules of
the game" — blueprint slots with hard requirements, and game maps (SE world
saves) with designated start positions — while team leaders (Commanders) and
builders (Engineers) supply the ships and assemble a match. The output of the
MVP is a ready-to-run copy of a world save with the selected ships injected at
their start positions.

## 2. Roles & permissions

| Role | Capabilities |
|---|---|
| **Game Admin** | Everything below, plus: manage users/roles, create Blueprint Slots, define blueprint requirements, upload Game Maps, define start slots on maps |
| **Commander** | Everything Member can, plus: "start a world" (select map + compatible blueprints → generate prepared world copy) |
| **Engineer** | Everything Member can, plus: upload blueprints into Blueprint Slots |
| **Member** | Read-only: browse slots, blueprints, maps, prepared worlds |

- New accounts default to **Member**.
- **Decision:** registration requires a shared **invite code** (configured by
  a Game Admin, rotatable); new users still land as Member.
- **Decision:** roles are **global** in the MVP — no team entity. Any
  Engineer can fill any slot; any Commander can start a world. Teams are a
  post-MVP layer (schema should not preclude adding a `team_id` later).
- **Decision:** roles form a **strict hierarchy**:
  `Game Admin ⊃ Commander ⊃ Engineer ⊃ Member` — a single ordered enum;
  Commanders can also upload blueprints, Admins can do everything.

## 3. Core domain objects

### 3.1 Ship Class & Blueprint Slot
**Decision:** requirements hang off a **Ship Class**; slots are typed
instances of a class.

- **Ship Class** (Game Admin): name (e.g. Battleship, Destroyer),
  description, **requirement set**. The requirement set is defined once on
  the class and applies to every slot of that class.
- **Blueprint Slot** (Game Admin): belongs to one Ship Class; holds **at
  most one** accepted blueprint. Admin creates N slots per class
  ("Battleship #1", "Battleship #2", …) to cap how many blueprints of that
  class exist in the pool. Fields: class, name/number, current blueprint
  (nullable), status (empty / filled).
- Start slots on maps support **classes**, not individual slots; a Commander
  can assign any filled slot whose class is supported.

### 3.2 Blueprint requirements (validation rules)
Defined per **Ship Class** by Game Admins; enforced by the system at upload
time. Upload is accepted **only if all requirements pass**.

**Decision — MVP rule types** (all parsed from the blueprint's `bp.sbc`):
- **Block count** (min/max) — total CubeBlocks across all grids
- **Grid size** — require Large-grid or Small-grid
- **PCU limit** — max total PCU; needs a block→PCU lookup table shipped with
  the app (extracted from SE game data; must be updatable as SE patches)
- **Weapon count** — max weapon blocks, counted against a maintained
  weapon-block-type list
- **Block whitelist/blacklist** — forbid or cap specific block types (e.g.
  no jump drives, max 2 gyros)

Post-MVP candidates: mass, dimensions, subgrid count, mod-block detection.

Validation report shown to the uploader on failure (which rules failed, and
measured vs. allowed values).

### 3.2a Block data: the PCU problem — **RESOLVED**

**Decisions:** hybrid sourcing (repo-shipped seed + admin re-upload) ·
unknown blocks **hard-fail** validation · **vanilla only** in MVP.

A blueprint's `bp.sbc` lists each block only by identity —
`<TypeId>/<SubtypeName>` (e.g. `LargeMissileTurret` /
`LargeCalibreTurret`). **PCU values are not in the blueprint**; they live in
SE's game-data definition files (`<SE install>/Content/Data/CubeBlocks*.sbc`,
plain XML, one `<Definition>` per block with a `<PCU>` element). The same is
true for "is this block a weapon" — so the PCU table and the weapon list are
really one problem: we need a **block definitions dataset**:

```
block_definitions(type_id, subtype_id, display_name, pcu,
                  is_weapon, grid_size, source, updated_at)
```

**Sourcing — hybrid.** An extractor script
(`scripts/extract_blockdata.py`) parses `CubeBlocks*.sbc` from a local SE
install into `data/block_definitions.json`, committed to the repo and seeded
into Postgres on migrate — the app works out of the box. Game Admins can
also upload newer `CubeBlocks*.sbc` files (or a zip of `Content/Data`)
through the admin UI to refresh the table after an SE patch; the server-side
parser is the same code as the extractor. Each refresh records `source` and
`updated_at`; the admin screen shows when block data was last updated.

**Unknown blocks — hard fail.** A blueprint containing any
`TypeId/SubtypeId` absent from the table is rejected, with the unknown types
listed ("ask an admin to update game data"). This prevents stale-table PCU
under-counts and doubles as the mod detector.

**Mods — out of scope for MVP.** Vanilla only; modded blueprints are
effectively rejected by the unknown-block rule. Mod support later is
cheap (same file format, tag definitions with a mod source) but adds admin
surface we don't need yet.

**Weapon detection.** Vanilla weapons are identifiable by TypeId
(`LargeMissileTurret`, `SmallGatlingGun`, `InteriorTurret`, …); we flag
`is_weapon` at extraction time from a TypeId list rather than maintaining a
separate hand-curated block list.

### 3.3 Blueprint upload (Engineer)
- SE blueprints live at `%AppData%/SpaceEngineers/Blueprints/local/<name>/`
  containing `bp.sbc` (XML), optionally `bp.sbcB5` (binary) and `thumb.png`.
- **Upload format:** a `.zip` of the blueprint folder (preferred — keeps the
  thumbnail), or a bare `bp.sbc`. `bp.sbcB5` is ignored/regenerable by SE.
- Server parses `bp.sbc`, runs the slot's class requirement set, stores the
  file in B2 on success, and records extracted stats (block count, PCU, grid
  size, weapon count, thumbnail) for display.
- **Decision — replacement:** slots are first-come, but **any Engineer can
  overwrite any filled slot** with a new blueprint that passes validation.
  Game Admins can clear slots. (Keep an upload history/audit trail so
  overwrites are visible.)

### 3.4 Game Map / World Save (Game Admin)
- SE world saves are folders with `Sandbox.sbc`, `SANDBOX_0_0_0_.sbs` (the
  big one — all grids/entities), `Sandbox_config.sbc`, etc. Upload as `.zip`.
- Fields: name, description, upload, list of **start slots**.
- **Start slot**: GPS coordinate + list of supported **Ship Classes**.
  Admin can paste an SE GPS string (`GPS:Name:X:Y:Z:#Color:`) and the app
  parses it, or enter X/Y/Z directly.
- **Decision:** position only in MVP — spawned ships use identity
  orientation. Orientation vectors are a post-MVP add for tight-space spawns
  (schema: nullable orientation columns from day one so no migration pain).

### 3.5 World start (Commander)
1. Commander picks a Game Map and gives the run a **name**.
2. For each start slot (up to N), picks a filled Blueprint Slot from that
   start slot's supported list (or leaves it empty).
3. System copies the world save, injects each blueprint's grids into the
   world file at the start slot's coordinates, **renames the save** (the
   Commander-given name written to `SessionName` in `Sandbox.sbc` /
   `Sandbox_config.sbc` and used as the save folder name), and stores the
   result as a new **Prepared World** in B2, downloadable as `.zip`.
4. **Retention:** prepared worlds **auto-expire 24 h** after they become
   ready — a janitor job deletes the B2 object and marks the row `expired`
   (metadata kept for history). The Commander can re-run the same
   assignments to regenerate.

Ship injection = merging the blueprint's `CubeGrids` into the save's `.sbs`
entity list with new EntityIds and repositioned coordinates. This is the
hardest technical piece and deserves an early spike.

- **Decision:** prepared worlds are always **downloadable as a zip**; if a
  dedicated server is configured (feature-flagged), the app can additionally
  **push the save to that server**. Download is the guaranteed MVP path;
  push is optional plumbing behind a flag.
- **Decision:** the concrete push transport is **deferred**. MVP defines the
  feature flag plus an abstract `WorldDeliverer` interface
  (`deliver(prepared_world) -> DeliveryResult`); the only shipped
  implementation is "download" (a no-op deliverer). SFTP / panel API / Torch
  becomes a concrete implementation when we get there.

## 4. Architecture

**Decisions:** Python **FastAPI** backend + **React** SPA frontend,
**Postgres**, **email/password auth**, files in **Backblaze B2**.

- **Backend: FastAPI** (Python 3.12+)
  - SQLAlchemy 2.0 + Alembic migrations, Pydantic v2 schemas.
  - Auth: email/password (argon2 hashing), **httpOnly cookie sessions**
    (first-party SPA — simpler and safer than JWT; sessions in Postgres).
  - Role-based authorization as a FastAPI dependency (`require_role(...)`)
    comparing against the ordered role enum.
  - XML processing: `lxml` for `bp.sbc`; `lxml.etree.iterparse` (streaming)
    for large `.sbs` world files.
- **Frontend: React** SPA — Vite + TypeScript, **Tailwind CSS** (custom warm
  theme tokens), **TanStack Query** for server state, React Router. No heavy
  component library — the PostHog-ish look is easier hand-rolled on Tailwind.
- **Postgres** for relational data (users, roles, slots, rules, maps, start
  slots, prepared worlds) — and for sessions and the job queue (below).
- **Backblaze B2** via its S3-compatible API (`boto3`) for all artifacts:
  blueprint zips, thumbnails, world save zips, prepared world zips. Nothing
  persisted on local disk beyond temp processing space. Downloads served via
  presigned URLs so world zips never stream through the API.
- **Background jobs: Postgres-backed queue** (a `jobs` table +
  `SELECT … FOR UPDATE SKIP LOCKED`, dedicated worker process). Avoids a
  Redis/Celery dependency entirely at MVP scale; the `prepared_worlds.status`
  column doubles as the user-visible job state, polled by the frontend.
- **Deployment: Docker Compose** — `api`, `worker`, `postgres`, and a
  `caddy`/`nginx` container serving the built SPA and proxying `/api`.

*(The four calls above — cookie sessions, Tailwind, Postgres-backed jobs,
Docker Compose — are proposed defaults; flag any you want changed.)*

## 5. Data model (first cut)

```
users(id, email UNIQUE, display_name, password_hash, role
      [admin|commander|engineer|member], created_at)
ship_classes(id, name, description, created_by, created_at)
requirements(id, ship_class_id, rule_type, params jsonb)
blueprint_slots(id, ship_class_id, name, created_by, created_at)
blueprints(id, slot_id, uploader_id, b2_key, stats jsonb, thumb_b2_key,
           status [active|replaced|cleared], created_at)
  -- one ACTIVE blueprint per slot (partial unique index on slot_id
  --  WHERE status='active'); replaced rows kept as audit history
game_maps(id, name, description, b2_key, uploaded_by, created_at)
start_slots(id, map_id, name, gps_x, gps_y, gps_z, position_index)
start_slot_classes(start_slot_id, ship_class_id)
prepared_worlds(id, map_id, name, created_by, b2_key, status
                [queued|processing|ready|failed|expired], error,
                expires_at, created_at)
prepared_world_assignments(prepared_world_id, start_slot_id, blueprint_id)
  -- blueprint_id pins the exact blueprint version used, surviving
  --  later slot overwrites
```

## 5a. API surface (sketch)

```
POST   /api/auth/register            {email, display_name, password, invite_code}
POST   /api/auth/login | /logout
GET    /api/auth/me

GET    /api/users                    (admin)      list + role management
PATCH  /api/users/{id}               (admin)      change role

GET    /api/ship-classes                          list w/ requirements
POST   /api/ship-classes             (admin)
PATCH  /api/ship-classes/{id}        (admin)      incl. requirement set
DELETE /api/ship-classes/{id}        (admin)

GET    /api/slots                                 list w/ class + fill state
POST   /api/slots                    (admin)
DELETE /api/slots/{id}               (admin)
POST   /api/slots/{id}/blueprint     (engineer+)  multipart upload → validate
                                                  → 201 w/ stats, or 422 w/
                                                  per-rule validation report
DELETE /api/slots/{id}/blueprint     (admin)      clear slot
GET    /api/blueprints/{id}                       stats/detail
GET    /api/blueprints/{id}/download              presigned B2 URL

GET    /api/maps                                  list w/ start slots
POST   /api/maps                     (admin)      multipart zip upload
PATCH  /api/maps/{id}                (admin)      start slot editor
DELETE /api/maps/{id}                (admin)

POST   /api/prepared-worlds          (commander+) {map_id, assignments:
                                                  [{start_slot_id, slot_id}]}
                                                  → enqueue job
GET    /api/prepared-worlds                       list
GET    /api/prepared-worlds/{id}                  status (poll target)
GET    /api/prepared-worlds/{id}/download         presigned B2 URL
POST   /api/prepared-worlds/{id}/deliver          (flagged) WorldDeliverer

GET    /api/block-definitions                     stats: count, updated_at
POST   /api/block-definitions        (admin)      upload CubeBlocks*.sbc /
                                                  Content-Data zip → refresh
GET    /api/settings | PATCH         (admin)      invite code, server flag
```

Validation errors return a structured report:
`{passed: false, results: [{rule, param, measured, allowed, passed}]}` —
rendered as the Engineer-facing checklist.

## 6. UI / design

- Warm yellow-beige aesthetic à la PostHog / koi.ai. First-cut tokens:
  - Background `#F5EFE6` (warm cream), surfaces `#FFFBF3`, borders `#E5DCC9`
  - Text `#1D1A16` (warm near-black), muted `#6B6355`
  - Accent `#F5B942` (warm amber) with dark-on-amber buttons; success/fail
    for validation states in warm-adjusted green/red
  - Chunky friendly sans (e.g. a PostHog-style humanist face), generous
    radii, card-based layout, subtle 1px borders over shadows
- Key screens: Login/Register (invite code) · Dashboard · Ship Classes
  (admin: requirements editor) · Blueprint Slots (grid of slot cards by
  class, fill state, upload flow w/ validation checklist) · Game Maps
  (list/detail w/ start-slot editor) · Start a World wizard (map →
  per-start-slot blueprint picker filtered by class → confirm → job
  progress → download) · Admin (users/roles, invite code, server flag).

## 7. Milestones (draft)

1. **Spike**: parse `bp.sbc`, extract stats; inject a blueprint into a small
   world save and verify it loads in SE. De-risks everything.
2. Auth + roles + user admin.
3. Blueprint Slots + requirements engine + Engineer upload w/ validation.
4. Game Maps upload + start slot editor.
5. Start-a-World wizard + world preparation job + prepared world downloads.
6. Design polish pass.

## 7a. Repo layout (proposed)

```
formula-se/
├── backend/
│   ├── app/
│   │   ├── api/            # routers: auth, users, classes, slots, maps, worlds
│   │   ├── core/           # config, security, deps (require_role)
│   │   ├── models/         # SQLAlchemy
│   │   ├── schemas/        # Pydantic
│   │   ├── services/       # b2.py, validation/, seformat/ (sbc/sbs parsing),
│   │   │                   # worldprep.py, deliverers/
│   │   └── worker.py       # job loop (Postgres SKIP LOCKED)
│   ├── data/               # block_definitions.json (extracted seed)
│   ├── scripts/            # extract_blockdata.py (run against SE install)
│   ├── alembic/
│   └── tests/              # incl. fixture blueprints & a small world save
├── frontend/
│   └── src/ (routes, components, api client, theme)
├── docker-compose.yml
└── PLAN.md
```

## 8. Decisions log

- ✅ Stack: Python FastAPI + React (Vite/TS) + Postgres
- ✅ Auth: email + password
- ✅ Roles: global, no teams in MVP; strict hierarchy
  Admin ⊃ Commander ⊃ Engineer ⊃ Member
- ✅ Output: downloadable prepared world always; optional push to a
  configured dedicated server behind a feature flag
- ✅ Slot model: Ship Classes carry the requirement set; slots are typed
  instances (one active blueprint each); start slots support classes
- ✅ Replacement: any Engineer may overwrite a filled slot (re-validated);
  Admins can clear; history kept
- ✅ MVP rules: block count, grid size, PCU limit, weapon count,
  block white/blacklist
- ✅ Registration gated by rotatable invite code
- ✅ Start slots are position-only in MVP (nullable orientation columns
  reserved in schema)
- ✅ Push transport deferred behind a `WorldDeliverer` interface; MVP ships
  download only
- ✅ Defaults (veto-able): cookie sessions · Tailwind + TanStack Query ·
  Postgres-backed job queue (no Redis) · Docker Compose deployment

- ✅ Spike/in-game verification: manual, done by admins before games —
  no in-app verification tooling needed
- ✅ Prepared worlds auto-expire after 24 h (janitor deletes B2 object,
  row kept as `expired`)
- ✅ "Start a world" renames the save (Commander-provided name →
  `SessionName` + folder name); otherwise a faithful copy + ships
- ✅ Block data (PCU/weapons): hybrid — repo-shipped extracted seed +
  admin re-upload of `CubeBlocks*.sbc`; unknown blocks hard-fail
  validation; vanilla only in MVP (see §3.2a)

## 9. Open questions (rolling list)

*(none — plan is decision-complete for MVP)*
