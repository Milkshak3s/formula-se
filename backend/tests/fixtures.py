"""Programmatic SE-format fixtures so tests don't need real game files."""
from __future__ import annotations

import io
import zipfile


def make_blueprint_xml(
    display_name: str = "Test Ship",
    grid_size: str = "Large",
    blocks: list[tuple[str, str]] | None = None,
    position: tuple[float, float, float] = (100.0, 200.0, 300.0),
) -> bytes:
    """Build a minimal but structurally-faithful bp.sbc.

    ``blocks`` is a list of (TypeId, SubtypeName). TypeId is serialized as the
    xsi:type ``MyObjectBuilder_<TypeId>`` just like the real format.
    """
    if blocks is None:
        blocks = [
            ("Cockpit", "LargeBlockCockpit"),
            ("Reactor", "LargeBlockLargeGenerator"),
            ("Gyro", "LargeBlockGyro"),
            ("Thrust", "LargeBlockLargeThrust"),
        ]
    block_xml = "\n".join(
        f"""        <MyObjectBuilder_CubeBlock xsi:type="MyObjectBuilder_{tid}">
          <SubtypeName>{sub}</SubtypeName>
          <EntityId>{1000 + i}</EntityId>
        </MyObjectBuilder_CubeBlock>"""
        for i, (tid, sub) in enumerate(blocks)
    )
    px, py, pz = position
    return f"""<?xml version="1.0"?>
<Definitions xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <ShipBlueprints>
    <ShipBlueprint>
      <Id Type="MyObjectBuilder_ShipBlueprintDefinition" Subtype="{display_name}" />
      <DisplayName>{display_name}</DisplayName>
      <CubeGrids>
        <CubeGrid>
          <EntityId>42</EntityId>
          <GridSizeEnum>{grid_size}</GridSizeEnum>
          <PositionAndOrientation>
            <Position x="{px}" y="{py}" z="{pz}" />
            <Forward x="0" y="0" z="-1" />
            <Up x="0" y="1" z="0" />
          </PositionAndOrientation>
          <CubeBlocks>
{block_xml}
          </CubeBlocks>
        </CubeGrid>
      </CubeGrids>
    </ShipBlueprint>
  </ShipBlueprints>
</Definitions>
""".encode()


def make_blueprint_zip(**kwargs) -> bytes:
    xml = make_blueprint_xml(**kwargs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("MyShip/bp.sbc", xml)
        zf.writestr("MyShip/thumb.png", b"\x89PNG\r\n\x1a\n-fake-thumbnail")
    return buf.getvalue()


def make_world_zip(session_name: str = "Original Session") -> bytes:
    sandbox_sbc = f"""<?xml version="1.0"?>
<MyObjectBuilder_Checkpoint xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <SessionName>{session_name}</SessionName>
  <GameMode>Survival</GameMode>
</MyObjectBuilder_Checkpoint>
""".encode()
    sandbox_config = f"""<?xml version="1.0"?>
<MyObjectBuilder_WorldConfiguration>
  <SessionName>{session_name}</SessionName>
</MyObjectBuilder_WorldConfiguration>
""".encode()
    sbs = b"""<?xml version="1.0"?>
<MyObjectBuilder_Sector xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <SectorObjects>
    <MyObjectBuilder_EntityBase xsi:type="MyObjectBuilder_VoxelMap">
      <EntityId>7</EntityId>
    </MyObjectBuilder_EntityBase>
  </SectorObjects>
</MyObjectBuilder_Sector>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("MyWorld/Sandbox.sbc", sandbox_sbc)
        zf.writestr("MyWorld/Sandbox_config.sbc", sandbox_config)
        zf.writestr("MyWorld/SANDBOX_0_0_0_.sbs", sbs)
    return buf.getvalue()
