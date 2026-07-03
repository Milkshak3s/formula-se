import io
import zipfile

from app.services.seformat.blueprint import extract_grids_xml
from app.services.seformat.worldsave import (
    GridPlacement,
    inject_into_sector,
    prepare_world,
)
from tests.fixtures import make_blueprint_xml, make_world_zip


def _read_member(zip_bytes: bytes, suffix: str) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(suffix))
        return zf.read(name).decode()


def test_inject_adds_grid_and_repositions():
    grids = extract_grids_xml(make_blueprint_xml(position=(0, 0, 0)))
    sector = make_world_zip()  # not used directly here
    # Extract the sector xml
    with zipfile.ZipFile(io.BytesIO(sector)) as zf:
        sbs = zf.read("MyWorld/SANDBOX_0_0_0_.sbs")

    placement = GridPlacement(grids_xml=grids, x=1000.0, y=2000.0, z=3000.0)
    result = inject_into_sector(sbs, [placement])
    text = result.decode()
    assert "MyObjectBuilder_CubeGrid" in text
    assert 'x="1000.0"' in text and 'y="2000.0"' in text and 'z="3000.0"' in text


def test_prepare_world_renames_and_injects():
    grids = extract_grids_xml(make_blueprint_xml(position=(0, 0, 0)))
    placement = GridPlacement(grids_xml=grids, x=500.0, y=0.0, z=0.0)
    out = prepare_world(
        make_world_zip("Original Session"),
        session_name="Match 1 — Finals",
        placements=[placement],
    )

    sandbox = _read_member(out, "sandbox.sbc")
    assert "Match 1 — Finals" in sandbox
    assert "Original Session" not in sandbox

    sbs = _read_member(out, ".sbs")
    assert "MyObjectBuilder_CubeGrid" in sbs
    assert 'x="500.0"' in sbs

    # Archive is re-rooted under a folder derived from the session name.
    with zipfile.ZipFile(io.BytesIO(out)) as zf:
        assert any("Match 1" in n for n in zf.namelist())


def test_entity_ids_reassigned():
    grids = extract_grids_xml(make_blueprint_xml(position=(0, 0, 0)))
    with zipfile.ZipFile(io.BytesIO(make_world_zip())) as zf:
        sbs = zf.read("MyWorld/SANDBOX_0_0_0_.sbs")
    result = inject_into_sector(
        sbs, [GridPlacement(grids_xml=grids, x=0, y=0, z=0)]
    ).decode()
    # Original blueprint EntityId 42 should have been replaced.
    assert "<EntityId>42</EntityId>" not in result


def _world_with_backup() -> bytes:
    """A world zip that also carries SE's local Backup/ folder of stale saves."""
    base = make_world_zip("Original Session")
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base)) as src, zipfile.ZipFile(
        buf, "w", zipfile.ZIP_DEFLATED
    ) as dst:
        for name in src.namelist():
            dst.writestr(name, src.read(name))
        # Add stale backup copies under Backup/ (deeper path than the main one).
        dst.writestr("MyWorld/Backup/2026-01-01 000000/SANDBOX_0_0_0_.sbs", b"<old/>")
        dst.writestr("MyWorld/Backup/2026-01-01 000000/Sandbox.sbc", b"<old/>")
    return buf.getvalue()


def test_prepare_world_drops_backup_folder():
    grids = extract_grids_xml(make_blueprint_xml(position=(0, 0, 0)))
    out = prepare_world(
        _world_with_backup(),
        session_name="Cleaned Match",
        placements=[GridPlacement(grids_xml=grids, x=10.0, y=0.0, z=0.0)],
    )
    with zipfile.ZipFile(io.BytesIO(out)) as zf:
        names = zf.namelist()
        # No Backup/ members survive.
        assert not any("/Backup/" in n or n.startswith("Backup/") for n in names)
        # Exactly one .sbs remains and it received the injected grid.
        sbs = [n for n in names if n.lower().endswith(".sbs")]
        assert len(sbs) == 1
        assert "MyObjectBuilder_CubeGrid" in zf.read(sbs[0]).decode()
