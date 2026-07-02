"""Parse a Space Engineers blueprint (``bp.sbc``) and extract grid/block data.

The blueprint XML looks (abridged) like::

    <Definitions ...>
      <ShipBlueprints>
        <ShipBlueprint>
          <Id .../>
          <DisplayName>My Ship</DisplayName>
          <CubeGrids>
            <CubeGrid>
              <GridSizeEnum>Large</GridSizeEnum>
              <CubeBlocks>
                <MyObjectBuilder_CubeBlock xsi:type="MyObjectBuilder_Reactor">
                  <SubtypeName>LargeBlockLargeGenerator</SubtypeName>
                  ...
                </MyObjectBuilder_CubeBlock>
              </CubeBlocks>
            </CubeGrid>
          </CubeGrids>
        </ShipBlueprint>
      </ShipBlueprints>
    </Definitions>

Every block carries a ``xsi:type="MyObjectBuilder_<TypeId>"`` attribute and a
``<SubtypeName>`` element. We normalize the TypeId by stripping the
``MyObjectBuilder_`` prefix so it matches the block-definitions dataset.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field

from lxml import etree

XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
_MOB_PREFIX = "MyObjectBuilder_"


@dataclass
class BlockRef:
    type_id: str
    subtype_id: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.type_id, self.subtype_id)


@dataclass
class GridInfo:
    grid_size: str  # "Large" | "Small"
    block_count: int


@dataclass
class ParsedBlueprint:
    display_name: str
    grids: list[GridInfo] = field(default_factory=list)
    blocks: list[BlockRef] = field(default_factory=list)

    @property
    def block_count(self) -> int:
        return len(self.blocks)

    @property
    def grid_sizes(self) -> set[str]:
        return {g.grid_size for g in self.grids}

    def block_type_counts(self) -> dict[tuple[str, str], int]:
        counts: dict[tuple[str, str], int] = {}
        for b in self.blocks:
            counts[b.key] = counts.get(b.key, 0) + 1
        return counts


class BlueprintParseError(ValueError):
    """Raised when a blueprint file cannot be understood."""


def _localname(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _normalize_type_id(xsi_type: str | None) -> str:
    if not xsi_type:
        return ""
    if xsi_type.startswith(_MOB_PREFIX):
        return xsi_type[len(_MOB_PREFIX):]
    return xsi_type


def extract_bp_sbc(raw: bytes, filename: str = "") -> bytes:
    """Return the ``bp.sbc`` XML bytes from an upload.

    Accepts either a raw ``bp.sbc`` or a ``.zip`` of the blueprint folder.
    """
    stripped = raw.lstrip()
    if stripped[:1] == b"<":
        return raw  # already XML

    if zipfile.is_zipfile(io.BytesIO(raw)):
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            candidates = [
                n for n in zf.namelist() if n.lower().endswith("bp.sbc")
            ]
            if not candidates:
                raise BlueprintParseError("Zip does not contain a bp.sbc file")
            # Prefer the shallowest path.
            candidates.sort(key=lambda n: n.count("/"))
            return zf.read(candidates[0])

    raise BlueprintParseError(
        "Upload must be a bp.sbc XML file or a .zip of the blueprint folder"
    )


def extract_thumbnail(raw: bytes) -> bytes | None:
    """Return thumb.png bytes if the upload is a zip that contains one."""
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        return None
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for n in zf.namelist():
            if n.lower().endswith("thumb.png"):
                return zf.read(n)
    return None


def parse_blueprint(bp_sbc: bytes) -> ParsedBlueprint:
    """Parse blueprint XML into structured grid/block data."""
    try:
        parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
        root = etree.fromstring(bp_sbc, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise BlueprintParseError(f"Invalid blueprint XML: {exc}") from exc

    if root is None:
        raise BlueprintParseError("Blueprint XML is empty or unparseable")

    display_name = ""
    for el in root.iter():
        if _localname(el.tag) == "DisplayName" and el.text:
            display_name = el.text.strip()
            break

    grids: list[GridInfo] = []
    blocks: list[BlockRef] = []

    for grid_el in root.iter():
        if _localname(grid_el.tag) != "CubeGrid":
            continue

        grid_size = "Large"
        grid_block_count = 0
        for child in grid_el.iter():
            ln = _localname(child.tag)
            if ln == "GridSizeEnum" and child.text:
                grid_size = child.text.strip()
            elif ln == "CubeBlocks":
                for block_el in child:
                    if not _localname(block_el.tag):
                        continue
                    xsi_type = block_el.get(f"{{{XSI_NS}}}type")
                    type_id = _normalize_type_id(xsi_type)
                    subtype = ""
                    for sub in block_el:
                        if _localname(sub.tag) == "SubtypeName":
                            subtype = (sub.text or "").strip()
                            break
                    blocks.append(BlockRef(type_id=type_id, subtype_id=subtype))
                    grid_block_count += 1

        grids.append(GridInfo(grid_size=grid_size, block_count=grid_block_count))

    if not grids:
        raise BlueprintParseError("Blueprint contains no CubeGrids")

    return ParsedBlueprint(display_name=display_name, grids=grids, blocks=blocks)


def extract_grids_xml(bp_sbc: bytes) -> bytes:
    """Return the serialized ``<CubeGrids>`` element(s) for world injection.

    Falls back to concatenated ``<CubeGrid>`` elements wrapped in a synthetic
    root so downstream parsing always sees valid XML.
    """
    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
    root = etree.fromstring(bp_sbc, parser=parser)
    if root is None:
        raise BlueprintParseError("Blueprint XML is empty or unparseable")

    for el in root.iter():
        if _localname(el.tag) == "CubeGrids":
            return etree.tostring(el)

    grid_blobs = [
        etree.tostring(el) for el in root.iter() if _localname(el.tag) == "CubeGrid"
    ]
    if not grid_blobs:
        raise BlueprintParseError("Blueprint contains no CubeGrids to inject")
    inner = b"".join(grid_blobs)
    return b"<CubeGrids>" + inner + b"</CubeGrids>"
