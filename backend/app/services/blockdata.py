"""Block-definitions parsing and DB loading.

The parser here is the *same code* used by ``scripts/extract_blockdata.py`` and
by the admin re-upload endpoint (PLAN §3.2a). It reads SE ``CubeBlocks*.sbc``
game-data XML and produces normalized block records with PCU + weapon flags.
"""
from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone

from lxml import etree
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.blockdata import BlockDefinition
from app.services.seformat.blueprint import _localname
from app.services.validation.engine import BlockDef, DictBlockLookup

# Vanilla weapon TypeIds — a block is flagged is_weapon by TypeId membership
# rather than a separate hand-curated list (PLAN §3.2a).
WEAPON_TYPE_IDS = {
    "SmallGatlingGun",
    "SmallMissileLauncher",
    "SmallMissileLauncherReload",
    "LargeGatlingTurret",
    "LargeMissileTurret",
    "InteriorTurret",
    "LargeCalibreTurret",
    "SmallCalibreTurret",
    "TurretBase",
    "Searchlight",
}


@dataclass
class RawBlockDef:
    type_id: str
    subtype_id: str
    display_name: str
    pcu: int
    is_weapon: bool
    grid_size: str

    def as_dict(self) -> dict:
        return {
            "type_id": self.type_id,
            "subtype_id": self.subtype_id,
            "display_name": self.display_name,
            "pcu": self.pcu,
            "is_weapon": self.is_weapon,
            "grid_size": self.grid_size,
        }


def _text(el: etree._Element, name: str) -> str | None:
    for child in el.iter():
        if _localname(child.tag) == name and child.text is not None:
            return child.text.strip()
    return None


def parse_cubeblocks_xml(xml: bytes) -> list[RawBlockDef]:
    """Parse a single CubeBlocks*.sbc file into block definitions."""
    parser = etree.XMLParser(recover=True, huge_tree=True, resolve_entities=False)
    root = etree.fromstring(xml, parser=parser)
    if root is None:
        return []

    out: list[RawBlockDef] = []
    for def_el in root.iter():
        if _localname(def_el.tag) != "Definition":
            continue
        # <Id><TypeId>..</TypeId><SubtypeId>..</SubtypeId></Id>
        id_el = None
        for child in def_el:
            if _localname(child.tag) == "Id":
                id_el = child
                break
        if id_el is None:
            continue
        type_id = _text(id_el, "TypeId") or ""
        subtype_id = _text(id_el, "SubtypeId") or ""
        if not type_id:
            continue
        display = _text(def_el, "DisplayName") or ""
        pcu_raw = _text(def_el, "PCU")
        try:
            pcu = int(pcu_raw) if pcu_raw is not None else 0
        except ValueError:
            pcu = 0
        grid_size = _text(def_el, "CubeSize") or ""
        is_weapon = type_id in WEAPON_TYPE_IDS
        out.append(
            RawBlockDef(
                type_id=type_id,
                subtype_id=subtype_id,
                display_name=display,
                pcu=pcu,
                is_weapon=is_weapon,
                grid_size=grid_size,
            )
        )
    return out


def parse_upload(raw: bytes) -> list[RawBlockDef]:
    """Parse an admin upload: a single .sbc, or a .zip of Content/Data."""
    if zipfile.is_zipfile(io.BytesIO(raw)):
        defs: list[RawBlockDef] = []
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for name in zf.namelist():
                low = name.lower()
                if low.endswith(".sbc") and "cubeblocks" in low.rsplit("/", 1)[-1]:
                    defs.extend(parse_cubeblocks_xml(zf.read(name)))
        return defs
    return parse_cubeblocks_xml(raw)


def load_seed_json(path: str) -> list[RawBlockDef]:
    with open(path, "rb") as f:
        payload = json.load(f)
    records = payload.get("blocks", payload) if isinstance(payload, dict) else payload
    return [
        RawBlockDef(
            type_id=r["type_id"],
            subtype_id=r.get("subtype_id", ""),
            display_name=r.get("display_name", ""),
            pcu=int(r.get("pcu", 0)),
            is_weapon=bool(r.get("is_weapon", False)),
            grid_size=r.get("grid_size", ""),
        )
        for r in records
    ]


def upsert_block_defs(db: Session, defs: list[RawBlockDef], source: str) -> int:
    """Bulk upsert block definitions keyed on (type_id, subtype_id)."""
    if not defs:
        return 0
    now = datetime.now(timezone.utc)
    rows = [
        {
            "type_id": d.type_id,
            "subtype_id": d.subtype_id,
            "display_name": d.display_name,
            "pcu": d.pcu,
            "is_weapon": d.is_weapon,
            "grid_size": d.grid_size,
            "source": source,
            "updated_at": now,
        }
        for d in defs
    ]
    stmt = pg_insert(BlockDefinition).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["type_id", "subtype_id"],
        set_={
            "display_name": stmt.excluded.display_name,
            "pcu": stmt.excluded.pcu,
            "is_weapon": stmt.excluded.is_weapon,
            "grid_size": stmt.excluded.grid_size,
            "source": stmt.excluded.source,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    db.execute(stmt)
    db.commit()
    return len(rows)


def build_lookup(db: Session) -> DictBlockLookup:
    """Load all block definitions from the DB into an in-memory lookup."""
    defs = db.execute(select(BlockDefinition)).scalars().all()
    return DictBlockLookup(
        [
            BlockDef(
                type_id=d.type_id,
                subtype_id=d.subtype_id,
                pcu=d.pcu,
                is_weapon=d.is_weapon,
                grid_size=d.grid_size,
            )
            for d in defs
        ]
    )


def block_data_stats(db: Session) -> dict:
    count = db.execute(select(func.count()).select_from(BlockDefinition)).scalar_one()
    last = db.execute(select(func.max(BlockDefinition.updated_at))).scalar_one()
    sources = db.execute(
        select(BlockDefinition.source, func.count())
        .group_by(BlockDefinition.source)
    ).all()
    return {
        "count": count,
        "updated_at": last.isoformat() if last else None,
        "sources": {s: c for s, c in sources},
    }
