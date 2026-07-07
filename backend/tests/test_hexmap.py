"""Pure-logic coverage for the sector map (no DB — the DB-bound generate/read
paths are exercised by the throwaway-Postgres smoke, per project convention)."""
from __future__ import annotations

from app.core.database import Base
from app.models.enums import HexTerrain
from app.models.hexmap import (
    DEFAULT_RADIUS,
    MAX_RADIUS,
    MIN_RADIUS,
    HexMap,
    HexTile,
    SectorTerrainMap,
)
from app.schemas.hexmap import HexMapOut, HexTileOut, TerrainMapOut, TerrainMapUpdate
from app.services.hexmap import (
    AXIAL_DIRECTIONS,
    clamp_radius,
    hex_distance,
    neighbors,
    terrain_for,
    tiles_in_radius,
)


def test_tables_are_registered_with_metadata():
    # Guards the app.models.__init__ import wiring (Alembic/create_all see them).
    tables = set(Base.metadata.tables)
    assert HexMap.__tablename__ == "hex_map"
    assert HexTile.__tablename__ == "hex_tiles"
    assert SectorTerrainMap.__tablename__ == "sector_terrain_maps"
    assert {"hex_map", "hex_tiles", "sector_terrain_maps"} <= tables


def test_terrain_map_fk_cascades_with_the_game_map():
    # Removing a GameMap must clear its terrain associations (reference-only).
    fk = list(SectorTerrainMap.__table__.foreign_keys)[0]
    assert fk.column.table.name == "game_maps"
    assert fk.ondelete == "CASCADE"


def test_terrain_map_update_defaults_to_clear():
    # A body with no game_map_id means "clear the association".
    assert TerrainMapUpdate().game_map_id is None


def test_hex_map_out_defaults_to_no_terrain_maps():
    m = HexMapOut(id=1, name="Campaign Sector", radius=2)
    assert m.terrain_maps == []


def test_tiles_in_radius_counts_the_centred_hexagon():
    # A hexagon of radius N has 3*N*(N+1)+1 tiles.
    assert len(tiles_in_radius(0)) == 1
    assert len(tiles_in_radius(1)) == 7
    assert len(tiles_in_radius(2)) == 19
    assert len(tiles_in_radius(DEFAULT_RADIUS)) == 3 * 4 * 5 + 1  # 61


def test_tiles_in_radius_is_hexagon_not_rhombus():
    # Every included tile satisfies the cube third-axis bound; corners excluded.
    r = 3
    coords = set(tiles_in_radius(r))
    for q, rr in coords:
        assert abs(q + rr) <= r
    # Rhombus corner (r, r) must NOT be present for a hexagon.
    assert (r, r) not in coords
    assert (0, 0) in coords


def test_tiles_are_unique():
    coords = tiles_in_radius(4)
    assert len(coords) == len(set(coords))


def test_hex_distance_basics():
    assert hex_distance(0, 0, 0, 0) == 0
    # Each neighbour is exactly one step away.
    for dq, dr in AXIAL_DIRECTIONS:
        assert hex_distance(0, 0, dq, dr) == 1
    # Two steps east.
    assert hex_distance(0, 0, 2, 0) == 2
    # Symmetric.
    assert hex_distance(1, -2, -1, 3) == hex_distance(-1, 3, 1, -2)


def test_neighbors_are_six_distinct_adjacent_hexes():
    ns = neighbors(2, -1)
    assert len(ns) == 6
    assert len(set(ns)) == 6
    for nq, nr in ns:
        assert hex_distance(2, -1, nq, nr) == 1


def test_clamp_radius_bounds():
    assert clamp_radius(0) == MIN_RADIUS
    assert clamp_radius(-5) == MIN_RADIUS
    assert clamp_radius(MAX_RADIUS + 10) == MAX_RADIUS
    assert clamp_radius(3) == 3


def test_terrain_for_is_deterministic_and_origin_is_star():
    assert terrain_for(0, 0) == HexTerrain.star_system
    # Deterministic: same coords → same terrain across calls.
    for q, r in tiles_in_radius(3):
        assert terrain_for(q, r) == terrain_for(q, r)


def test_terrain_spread_favours_deep_space():
    counts: dict[HexTerrain, int] = {}
    for q, r in tiles_in_radius(MAX_RADIUS):
        t = terrain_for(q, r)
        counts[t] = counts.get(t, 0) + 1
    # Empty space should dominate a generated map.
    assert counts[HexTerrain.deep_space] == max(counts.values())


def test_schema_round_trips_from_attributes():
    import uuid

    tile = HexTile(
        id=uuid.uuid4(),
        q=1,
        r=-2,
        terrain=HexTerrain.nebula,
        name="Rift",
        station_limit=2,
    )
    out = HexTileOut.model_validate(tile)
    assert out.q == 1 and out.r == -2
    assert out.terrain == HexTerrain.nebula
    assert out.name == "Rift"
    assert out.station_limit == 2

    tm = TerrainMapOut(
        terrain=HexTerrain.planet, game_map_id=uuid.uuid4(), game_map_name="Barren World"
    )
    m = HexMapOut(id=1, name="Campaign Sector", radius=2, tiles=[out], terrain_maps=[tm])
    assert m.radius == 2
    assert m.tiles[0].terrain == HexTerrain.nebula
    assert m.terrain_maps[0].game_map_name == "Barren World"
