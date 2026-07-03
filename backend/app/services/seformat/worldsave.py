"""Read a Space Engineers world save, inject blueprint grids, and rename it.

A world save is a folder (uploaded/stored as a ``.zip``) containing:

* ``Sandbox.sbc`` / ``Sandbox_config.sbc`` — session metadata incl.
  ``<SessionName>``.
* ``SANDBOX_0_0_0_.sbs`` — the sector file whose ``<SectorObjects>`` list holds
  every grid/entity in the world.

Injection merges a blueprint's ``<CubeGrid>`` elements into ``<SectorObjects>``
as ``<MyObjectBuilder_CubeGrid>`` entities, giving every entity a fresh EntityId
(to avoid collisions) and repositioning the grids to a target coordinate.

This is a best-effort MVP: position-only placement with identity orientation,
per the PLAN. It preserves relative offsets between grids in a multi-grid
blueprint.
"""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

from lxml import etree

from app.services.seformat.blueprint import _localname

XSI = "http://www.w3.org/2001/XMLSchema-instance"


@dataclass
class GridPlacement:
    """One blueprint's grids to inject at a world coordinate."""

    grids_xml: bytes  # serialized <CubeGrids>...</CubeGrids> or list of CubeGrid
    x: float
    y: float
    z: float


class WorldSaveError(ValueError):
    pass


# Simple monotonic EntityId generator seeded from a large base to avoid
# colliding with existing ids. Deterministic given a seed so runs are testable.
class EntityIdAllocator:
    def __init__(self, seed: int = 5_000_000_000_000_000_000):
        self._next = seed

    def allocate(self) -> int:
        val = self._next
        self._next += 17  # arbitrary stride
        return val


def _find_member(zf: zipfile.ZipFile, suffix: str) -> str | None:
    matches = [n for n in zf.namelist() if n.lower().endswith(suffix.lower())]
    matches.sort(key=lambda n: n.count("/"))
    return matches[0] if matches else None


def _set_session_name(xml: bytes, new_name: str) -> bytes:
    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
    root = etree.fromstring(xml, parser=parser)
    if root is None:
        return xml
    changed = False
    for el in root.iter():
        if _localname(el.tag) == "SessionName":
            el.text = new_name
            changed = True
    if not changed:
        # Insert a SessionName as the first child if the schema lacked one.
        se = etree.SubElement(root, "SessionName")
        se.text = new_name
    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def _grid_position(grid_el: etree._Element) -> tuple[float, float, float] | None:
    for el in grid_el.iter():
        if _localname(el.tag) == "PositionAndOrientation":
            pos = None
            for child in el:
                if _localname(child.tag) == "Position":
                    pos = child
                    break
            if pos is not None:
                try:
                    return (
                        float(pos.get("x", "0")),
                        float(pos.get("y", "0")),
                        float(pos.get("z", "0")),
                    )
                except (TypeError, ValueError):
                    return None
    return None


def _translate_grid(grid_el: etree._Element, dx: float, dy: float, dz: float) -> None:
    """Shift the grid's top-level PositionAndOrientation by (dx,dy,dz)."""
    for el in grid_el.iter():
        if _localname(el.tag) != "PositionAndOrientation":
            continue
        for child in el:
            if _localname(child.tag) == "Position":
                try:
                    child.set("x", repr(float(child.get("x", "0")) + dx))
                    child.set("y", repr(float(child.get("y", "0")) + dy))
                    child.set("z", repr(float(child.get("z", "0")) + dz))
                except (TypeError, ValueError):
                    pass
        break  # only the grid's own position, not nested block orientations


def _remap_entity_ids(
    grids: list[etree._Element], alloc: EntityIdAllocator
) -> None:
    """Reassign every EntityId across a placement's grids and rewrite all
    in-ship references so the ship stays assembled.

    Multi-grid ships (rotors/pistons/hinges/wheels) link subgrids by EntityId
    via reference fields like ``TopBlockId``/``ParentEntityId``/``BlockEntityId``.
    We build one old→new map from every ``<EntityId>`` definition, then rewrite
    the text of *any* element whose value matches a reassigned id. EntityIds are
    64-bit values, so this never collides with small counters (e.g. inventory
    ``nextItemId``) or float coordinates. Reassigning also guarantees the
    injected entities never clash with EntityIds already in the world.
    """
    id_map: dict[str, str] = {}
    for grid in grids:
        for el in grid.iter():
            if _localname(el.tag) == "EntityId" and el.text:
                old = el.text.strip()
                if old and old != "0" and old not in id_map:
                    id_map[old] = str(alloc.allocate())
    if not id_map:
        return
    for grid in grids:
        for el in grid.iter():
            if el.text is not None and el.text.strip() in id_map:
                el.text = id_map[el.text.strip()]


def _blueprint_grid_elements(grids_xml: bytes) -> list[etree._Element]:
    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
    root = etree.fromstring(grids_xml, parser=parser)
    if root is None:
        raise WorldSaveError("Could not parse blueprint grids for injection")
    grids: list[etree._Element] = []
    for el in root.iter():
        if _localname(el.tag) == "CubeGrid":
            grids.append(el)
    if _localname(root.tag) == "CubeGrid":
        grids.append(root)
    return grids


def _to_sector_entity(grid_el: etree._Element) -> etree._Element:
    """Clone a blueprint <CubeGrid> as a sector entity.

    SE serializes every ``<SectorObjects>`` item as
    ``<MyObjectBuilder_EntityBase xsi:type="MyObjectBuilder_CubeGrid">`` — the
    element name is always the *base* type and the concrete type is carried in
    the ``xsi:type`` attribute. Emitting ``<MyObjectBuilder_CubeGrid>`` directly
    makes SE's list deserializer skip the entity, so the grid is present in the
    file but never loaded into the world.
    """
    nsmap = {"xsi": XSI}
    new_el = etree.Element("MyObjectBuilder_EntityBase", nsmap=nsmap)
    new_el.set(f"{{{XSI}}}type", "MyObjectBuilder_CubeGrid")
    for child in grid_el:
        new_el.append(_deepcopy(child))
    return new_el


def _deepcopy(el: etree._Element) -> etree._Element:
    return etree.fromstring(etree.tostring(el))


def inject_into_sector(
    sector_xml: bytes,
    placements: list[GridPlacement],
    alloc: EntityIdAllocator | None = None,
) -> bytes:
    """Return sector XML with all placements' grids injected."""
    alloc = alloc or EntityIdAllocator()
    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
    root = etree.fromstring(sector_xml, parser=parser)
    if root is None:
        raise WorldSaveError("Could not parse sector (.sbs) file")

    sector_objects = None
    for el in root.iter():
        if _localname(el.tag) == "SectorObjects":
            sector_objects = el
            break
    if sector_objects is None:
        sector_objects = etree.SubElement(root, "SectorObjects")

    for placement in placements:
        grids = _blueprint_grid_elements(placement.grids_xml)
        if not grids:
            continue
        # Anchor on the first grid; preserve relative offsets for the rest.
        anchor = _grid_position(grids[0]) or (0.0, 0.0, 0.0)
        dx = placement.x - anchor[0]
        dy = placement.y - anchor[1]
        dz = placement.z - anchor[2]
        for grid in grids:
            _translate_grid(grid, dx, dy, dz)
        # Reassign EntityIds across the whole ship at once so cross-grid
        # references (subgrid links) are rewritten consistently.
        _remap_entity_ids(grids, alloc)
        for grid in grids:
            sector_objects.append(_to_sector_entity(grid))

    return etree.tostring(root, xml_declaration=True, encoding="utf-8")


def prepare_world(
    world_zip: bytes,
    session_name: str,
    placements: list[GridPlacement],
    folder_name: str | None = None,
) -> bytes:
    """Produce a new prepared-world ``.zip`` from a source world save.

    * Renames the session (``SessionName`` in Sandbox.sbc / Sandbox_config.sbc).
    * Injects all blueprint grids into the sector file.
    * Re-roots the archive under ``folder_name`` (defaults to ``session_name``).
    """
    if not zipfile.is_zipfile(io.BytesIO(world_zip)):
        raise WorldSaveError("World save upload must be a .zip archive")

    folder = _safe_folder_name(folder_name or session_name)
    alloc = EntityIdAllocator()

    out_buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(world_zip)) as src, zipfile.ZipFile(
        out_buf, "w", zipfile.ZIP_DEFLATED
    ) as dst:
        sbs_name = _find_member(src, "sbs")
        if sbs_name is None:
            raise WorldSaveError("World save is missing a SANDBOX .sbs sector file")

        # Detect a common top-level folder in the source to strip it.
        common_prefix = _common_prefix(src.namelist())

        for name in src.namelist():
            if name.endswith("/"):
                continue
            rel = name[len(common_prefix):] if common_prefix else name
            # Drop SE's local Backup/ folder — stale sector copies from the
            # source save that only bloat the prepared world. SE regenerates
            # its own backups; only the main SANDBOX_*.sbs is ever loaded.
            if rel.split("/", 1)[0].lower() == "backup":
                continue
            data = src.read(name)
            lname = name.lower()
            if lname.endswith("sandbox.sbc") or lname.endswith("sandbox_config.sbc"):
                data = _set_session_name(data, session_name)
            elif name == sbs_name:
                data = inject_into_sector(data, placements, alloc)
            dst.writestr(f"{folder}/{rel}", data)

    return out_buf.getvalue()


def _common_prefix(names: list[str]) -> str:
    tops = {n.split("/", 1)[0] + "/" for n in names if "/" in n}
    if len(tops) == 1:
        only = next(iter(tops))
        # Only strip if *every* file lives under it.
        if all(n.startswith(only) for n in names):
            return only
    return ""


def _safe_folder_name(name: str) -> str:
    keep = [c if c.isalnum() or c in " -_." else "_" for c in name.strip()]
    cleaned = "".join(keep).strip() or "PreparedWorld"
    return cleaned[:100]
