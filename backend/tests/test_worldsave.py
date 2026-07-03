import io
import zipfile

from lxml import etree

from app.services.seformat.blueprint import _localname, extract_grids_xml
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
    assert 'x="1000.0"' in text and 'y="2000.0"' in text and 'z="3000.0"' in text

    # The grid must be serialized as an EntityBase list item with an xsi:type
    # discriminator — SE skips the entity if the element name is the concrete
    # type instead of MyObjectBuilder_EntityBase.
    root = etree.fromstring(result)
    XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"
    entities = [
        e
        for e in root.iter()
        if _localname(e.tag) == "MyObjectBuilder_EntityBase"
        and e.get(XSI) == "MyObjectBuilder_CubeGrid"
    ]
    assert len(entities) == 1
    # And never emitted as a bare concrete-type element.
    assert not any(_localname(e.tag) == "MyObjectBuilder_CubeGrid" for e in root.iter())


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


def test_multigrid_subgrid_references_remapped():
    """A subgrid link (base.TopBlockId -> top part EntityId on another grid)
    must survive EntityId reassignment, or the ship spawns disassembled."""
    grids_xml = b"""<CubeGrids>
      <CubeGrid>
        <EntityId>100</EntityId>
        <GridSizeEnum>Large</GridSizeEnum>
        <PositionAndOrientation><Position x="0" y="0" z="0"/></PositionAndOrientation>
        <CubeBlocks>
          <MyObjectBuilder_CubeBlock xsi:type="MyObjectBuilder_MotorStator"
              xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <SubtypeName>LargeStator</SubtypeName>
            <EntityId>200</EntityId>
            <TopBlockId>300</TopBlockId>
          </MyObjectBuilder_CubeBlock>
        </CubeBlocks>
      </CubeGrid>
      <CubeGrid>
        <EntityId>101</EntityId>
        <GridSizeEnum>Large</GridSizeEnum>
        <PositionAndOrientation><Position x="2.5" y="0" z="0"/></PositionAndOrientation>
        <CubeBlocks>
          <MyObjectBuilder_CubeBlock xsi:type="MyObjectBuilder_MotorRotor"
              xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
            <SubtypeName>LargeRotor</SubtypeName>
            <EntityId>300</EntityId>
          </MyObjectBuilder_CubeBlock>
        </CubeBlocks>
      </CubeGrid>
    </CubeGrids>"""

    with zipfile.ZipFile(io.BytesIO(make_world_zip())) as zf:
        sbs = zf.read("MyWorld/SANDBOX_0_0_0_.sbs")

    out = inject_into_sector(sbs, [GridPlacement(grids_xml=grids_xml, x=1000, y=0, z=0)])
    root = etree.fromstring(out)

    def texts(tag):
        return [e.text.strip() for e in root.iter() if _localname(e.tag) == tag and e.text]

    entity_ids = set(texts("EntityId"))
    top_block_ids = texts("TopBlockId")

    # Old ids are gone; the base still points at the (now-renamed) rotor top,
    # and that target exists among the injected EntityIds.
    assert "300" not in entity_ids and "300" not in top_block_ids
    assert len(top_block_ids) == 1
    assert top_block_ids[0] in entity_ids
    # Relative offset between the two grids is preserved (2.5m apart).
    xs = sorted(float(p.get("x")) for p in root.iter() if _localname(p.tag) == "Position")
    assert round(xs[1] - xs[0], 3) == 2.5


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


def _world_with_binary_mirror() -> bytes:
    """A world zip carrying the binary sector/checkpoint mirrors SE writes
    alongside the XML (SANDBOX_*.sbsB5). SE loads these in preference to the XML,
    so a prepared world must not keep the stale binary."""
    base = make_world_zip("Original Session")
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base)) as src, zipfile.ZipFile(
        buf, "w", zipfile.ZIP_DEFLATED
    ) as dst:
        for name in src.namelist():
            dst.writestr(name, src.read(name))
        dst.writestr("MyWorld/SANDBOX_0_0_0_.sbsB5", b"STALE-BINARY-SECTOR")
    return buf.getvalue()


def test_prepare_world_drops_binary_mirror():
    grids = extract_grids_xml(make_blueprint_xml(position=(0, 0, 0)))
    out = prepare_world(
        _world_with_binary_mirror(),
        session_name="No Stale Binary",
        placements=[GridPlacement(grids_xml=grids, x=5.0, y=0.0, z=0.0)],
    )
    with zipfile.ZipFile(io.BytesIO(out)) as zf:
        names = zf.namelist()
        # The stale binary must be gone so SE loads our injected XML sector.
        assert not any(n.lower().endswith("b5") for n in names), names
        sbs = [n for n in names if n.lower().endswith(".sbs")]
        assert len(sbs) == 1
        assert "MyObjectBuilder_CubeGrid" in zf.read(sbs[0]).decode()
