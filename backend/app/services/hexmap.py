"""Sector-map logic: axial-hex geometry and grid generation.

The geometry helpers (:func:`hex_distance`, :func:`neighbors`,
:func:`tiles_in_radius`) are pure and DB-free — they are the foundation the
future ship-movement and station-adjacency features build on, and are unit
tested in isolation. :func:`get_map` / :func:`generate_tiles` own the singleton
map row and its hex set.
"""
from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.enums import HexTerrain
from app.models.hexmap import (
    DEFAULT_RADIUS,
    MAX_RADIUS,
    MIN_RADIUS,
    SINGLETON_ID,
    HexMap,
    HexTile,
    SectorTerrainMap,
)

# The six axial neighbour directions (pointy-top), in clockwise order from East.
AXIAL_DIRECTIONS: tuple[tuple[int, int], ...] = (
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, 0),
    (-1, 1),
    (0, 1),
)


def hex_distance(aq: int, ar: int, bq: int, br: int) -> int:
    """Number of steps between two axial hexes (the future ship-move cost)."""
    return (abs(aq - bq) + abs(ar - br) + abs((aq + ar) - (bq + br))) // 2


def neighbors(q: int, r: int) -> list[tuple[int, int]]:
    """The six axial coordinates adjacent to ``(q, r)`` (unbounded by the map)."""
    return [(q + dq, r + dr) for dq, dr in AXIAL_DIRECTIONS]


def tiles_in_radius(radius: int) -> list[tuple[int, int]]:
    """Axial coords of every hex within a hexagon of the given radius.

    Radius 0 is the single centre hex; radius N adds N rings around it, for
    ``3 * N * (N + 1) + 1`` tiles total. Ordered by (q, r) for stable output.
    """
    coords: list[tuple[int, int]] = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            # Hexagon (not rhombus) shape: the third cube axis must also fit.
            if abs(q + r) <= radius:
                coords.append((q, r))
    return coords


def clamp_radius(radius: int) -> int:
    """Coerce a requested radius into the supported range."""
    return max(MIN_RADIUS, min(MAX_RADIUS, radius))


# Constellation-flavoured prefixes for auto-generated sector designations. Kept
# short (<= 8 chars) so "Prefix-NNN" stays legible on the map's hex labels.
SECTOR_PREFIXES: tuple[str, ...] = (
    "Kepler", "Gliese", "Cygnus", "Lyra", "Orion", "Draco", "Hydra", "Vela",
    "Corvus", "Auriga", "Perseus", "Phoenix", "Aquila", "Carina", "Tucana",
    "Pyxis", "Norma", "Octans", "Mensa", "Dorado", "Volans", "Crux", "Lupus",
    "Musca", "Grus", "Pavo", "Indus", "Antlia",
)

# The origin is the campaign's home sector; give it a stable, evocative name
# rather than a catalogue designation.
ORIGIN_SECTOR_NAME = "Homeport"


def _mix64(n: int) -> int:
    """A splitmix64 finalizer — scrambles an int to a well-distributed 64-bit hash.

    Used so the sector-name prefix and number spread evenly over the grid (a
    naive ``a*q ^ b*r`` clusters badly once taken modulo a small table size).
    """
    mask = 0xFFFFFFFFFFFFFFFF
    n &= mask
    n = ((n ^ (n >> 30)) * 0xBF58476D1CE4E5B9) & mask
    n = ((n ^ (n >> 27)) * 0x94D049BB133111EB) & mask
    return n ^ (n >> 31)


def name_for(q: int, r: int) -> str:
    """Deterministically name a sector from its coordinates (a catalogue code).

    Like :func:`terrain_for`, this is pure and RNG-free so the map is
    reproducible and testable. Produces designations such as ``"Kepler-472"``
    from two independent coordinate hashes (prefix + 3-digit number), giving
    enough variety that collisions across a map are rare. The origin gets a
    fixed home name. Admins can still override any sector's name.
    """
    if q == 0 and r == 0:
        return ORIGIN_SECTOR_NAME
    # Pack the signed coords into one key, then derive two independent hashes so
    # the prefix and number vary apart.
    key = ((q & 0xFFFFFFFF) << 32) | (r & 0xFFFFFFFF)
    prefix = SECTOR_PREFIXES[_mix64(key) % len(SECTOR_PREFIXES)]
    number = 100 + (_mix64(key ^ 0x9E3779B97F4A7C15) % 900)
    return f"{prefix}-{number}"


def terrain_for(q: int, r: int) -> HexTerrain:
    """Deterministically pick a hex's terrain from its coordinates.

    Deterministic (no RNG) so the generated map is reproducible and testable.
    The origin is always the home ``star_system``; everything else is a weighted
    spread biased heavily toward empty ``deep_space``.
    """
    if q == 0 and r == 0:
        return HexTerrain.star_system
    # Cheap, well-mixed hash of the coordinate pair.
    h = (q * 73856093) ^ (r * 19349663) ^ ((q + r) * 83492791)
    bucket = h % 100
    if bucket < 58:
        return HexTerrain.deep_space
    if bucket < 73:
        return HexTerrain.asteroid_field
    if bucket < 84:
        return HexTerrain.nebula
    if bucket < 92:
        return HexTerrain.ice_field
    if bucket < 98:
        return HexTerrain.planet
    return HexTerrain.star_system


def get_map(db: Session) -> HexMap:
    """Return the singleton sector map, creating it (at DEFAULT_RADIUS) if absent."""
    m = db.get(HexMap, SINGLETON_ID)
    if m is None:
        m = HexMap(id=SINGLETON_ID, radius=DEFAULT_RADIUS)
        db.add(m)
        try:
            db.commit()
        except IntegrityError:
            # Another worker/replica created it first — reuse that row.
            db.rollback()
            m = db.get(HexMap, SINGLETON_ID)
        else:
            db.refresh(m)
    return m


def generate_tiles(db: Session, radius: int) -> int:
    """Rebuild the hex set for the given radius and persist the new radius.

    Replaces every existing tile (a full regenerate). Safe to call repeatedly;
    returns the number of tiles created. Callers commit.
    """
    radius = clamp_radius(radius)
    m = get_map(db)
    m.radius = radius
    db.execute(delete(HexTile))
    db.flush()
    coords = tiles_in_radius(radius)
    db.add_all(
        HexTile(q=q, r=r, terrain=terrain_for(q, r), name=name_for(q, r))
        for q, r in coords
    )
    return len(coords)


def get_terrain_maps(db: Session) -> list[SectorTerrainMap]:
    """Return every terrain→map association, with the GameMap eagerly loaded."""
    return list(
        db.execute(
            select(SectorTerrainMap).options(
                selectinload(SectorTerrainMap.game_map)
            )
        )
        .scalars()
        .all()
    )


def set_terrain_map(
    db: Session, terrain: HexTerrain, game_map_id: uuid.UUID | None
) -> SectorTerrainMap | None:
    """Assign (or clear) the GameMap backing a terrain type. Caller commits.

    ``game_map_id=None`` removes the association (the terrain reverts to no map).
    Returns the resulting association row, or ``None`` when cleared.
    """
    row = db.get(SectorTerrainMap, terrain)
    if game_map_id is None:
        if row is not None:
            db.delete(row)
        return None
    if row is None:
        row = SectorTerrainMap(terrain=terrain, game_map_id=game_map_id)
        db.add(row)
    else:
        row.game_map_id = game_map_id
    return row


def ensure_tiles(db: Session) -> int:
    """Generate the default grid on first boot if the map has no tiles yet.

    Idempotent — a no-op once tiles exist, so it is safe in ``run_seeds`` which
    runs on every startup. Returns the number of tiles created (0 if present).
    """
    m = get_map(db)
    count = db.execute(select(func.count()).select_from(HexTile)).scalar_one()
    if count:
        return 0
    created = generate_tiles(db, m.radius)
    db.commit()
    return created


def ensure_tile_names(db: Session) -> int:
    """Backfill a generated name onto any sector that has none. Commits.

    Idempotent and safe in ``run_seeds``: only touches tiles whose ``name`` is
    empty, so admin-set names and already-generated names are left alone. This
    is how existing campaigns (whose tiles predate auto-naming) pick up names
    without a data migration. Returns the number of tiles named.
    """
    tiles = (
        db.execute(select(HexTile).where(HexTile.name == "")).scalars().all()
    )
    for tile in tiles:
        tile.name = name_for(tile.q, tile.r)
    if tiles:
        db.commit()
    return len(tiles)
