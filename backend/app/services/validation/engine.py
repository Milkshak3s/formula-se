"""Blueprint validation engine.

Given a :class:`ParsedBlueprint`, the ship class's requirement set, and a
block-definitions lookup, produce a structured pass/fail report. Uploads are
accepted only when every rule passes.

The unknown-block rule is enforced unconditionally (PLAN §3.2a): any block whose
``TypeId/SubtypeId`` is absent from the dataset hard-fails validation and doubles
as the mod detector.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from app.models.enums import RequirementType
from app.services.seformat.blueprint import ParsedBlueprint


@dataclass
class BlockDef:
    type_id: str
    subtype_id: str
    pcu: int
    is_weapon: bool
    grid_size: str


class BlockLookup(Protocol):
    def get(self, type_id: str, subtype_id: str) -> BlockDef | None: ...


class DictBlockLookup:
    """In-memory lookup keyed by (type_id, subtype_id), with a type-only fallback."""

    def __init__(self, defs: list[BlockDef]):
        self._by_pair: dict[tuple[str, str], BlockDef] = {}
        self._by_type: dict[str, BlockDef] = {}
        for d in defs:
            self._by_pair[(d.type_id, d.subtype_id)] = d
            self._by_type.setdefault(d.type_id, d)

    def get(self, type_id: str, subtype_id: str) -> BlockDef | None:
        hit = self._by_pair.get((type_id, subtype_id))
        if hit is not None:
            return hit
        # Some blocks legitimately have an empty subtype; fall back to type.
        if subtype_id == "":
            return self._by_type.get(type_id)
        return None


@dataclass
class RuleResult:
    rule: str
    param: dict[str, Any]
    measured: Any
    allowed: Any
    passed: bool
    detail: str = ""


@dataclass
class ValidationReport:
    passed: bool
    results: list[RuleResult] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "results": [asdict(r) for r in self.results],
            "stats": self.stats,
        }


def compute_stats(bp: ParsedBlueprint, lookup: BlockLookup) -> dict[str, Any]:
    """Aggregate PCU, weapon count, grid sizes, and unknown blocks."""
    total_pcu = 0
    weapon_count = 0
    unknown: set[str] = set()
    for block in bp.blocks:
        bd = lookup.get(block.type_id, block.subtype_id)
        if bd is None:
            unknown.add(f"{block.type_id}/{block.subtype_id}")
            continue
        total_pcu += bd.pcu
        if bd.is_weapon:
            weapon_count += 1
    return {
        "display_name": bp.display_name,
        "block_count": bp.block_count,
        "grid_count": len(bp.grids),
        "grid_sizes": sorted(bp.grid_sizes),
        "pcu": total_pcu,
        "weapon_count": weapon_count,
        "unknown_blocks": sorted(unknown),
    }


def _check_block_count(params: dict, stats: dict) -> RuleResult:
    lo = params.get("min")
    hi = params.get("max")
    count = stats["block_count"]
    ok = True
    if lo is not None and count < lo:
        ok = False
    if hi is not None and count > hi:
        ok = False
    return RuleResult(
        rule=RequirementType.block_count.value,
        param={"min": lo, "max": hi},
        measured=count,
        allowed={"min": lo, "max": hi},
        passed=ok,
    )


def _check_grid_size(params: dict, stats: dict) -> RuleResult:
    required = params.get("size")
    sizes = stats["grid_sizes"]
    # All grids must be the required size.
    ok = bool(required) and all(s == required for s in sizes)
    return RuleResult(
        rule=RequirementType.grid_size.value,
        param={"size": required},
        measured=sizes,
        allowed=required,
        passed=ok,
    )


def _check_pcu_limit(params: dict, stats: dict) -> RuleResult:
    hi = params.get("max")
    pcu = stats["pcu"]
    ok = hi is None or pcu <= hi
    return RuleResult(
        rule=RequirementType.pcu_limit.value,
        param={"max": hi},
        measured=pcu,
        allowed=hi,
        passed=ok,
    )


def _check_weapon_count(params: dict, stats: dict) -> RuleResult:
    hi = params.get("max")
    wc = stats["weapon_count"]
    ok = hi is None or wc <= hi
    return RuleResult(
        rule=RequirementType.weapon_count.value,
        param={"max": hi},
        measured=wc,
        allowed=hi,
        passed=ok,
    )


def _check_whitelist(params: dict, bp: ParsedBlueprint) -> RuleResult:
    allowed_types = set(params.get("type_ids", []))
    allowed_subtypes = set(params.get("subtype_ids", []))
    violations: list[str] = []
    for key, _count in bp.block_type_counts().items():
        type_id, subtype_id = key
        if type_id in allowed_types or subtype_id in allowed_subtypes:
            continue
        violations.append(f"{type_id}/{subtype_id}")
    return RuleResult(
        rule=RequirementType.block_whitelist.value,
        param={"type_ids": sorted(allowed_types), "subtype_ids": sorted(allowed_subtypes)},
        measured=sorted(set(violations)),
        allowed="only whitelisted blocks",
        passed=not violations,
        detail="Blocks not on the whitelist" if violations else "",
    )


def _check_blacklist(params: dict, bp: ParsedBlueprint) -> RuleResult:
    rules = params.get("rules", [])
    counts = bp.block_type_counts()
    violations: list[str] = []
    for rule in rules:
        tid = rule.get("type_id")
        sid = rule.get("subtype_id")
        maxn = rule.get("max", 0)
        total = 0
        for (btype, bsub), c in counts.items():
            if tid and btype != tid:
                continue
            if sid and bsub != sid:
                continue
            total += c
        if total > maxn:
            label = sid or tid or "block"
            violations.append(f"{label}: {total} > {maxn}")
    return RuleResult(
        rule=RequirementType.block_blacklist.value,
        param={"rules": rules},
        measured=violations,
        allowed="within blacklist caps",
        passed=not violations,
        detail="; ".join(violations),
    )


_STATS_CHECKERS = {
    RequirementType.block_count: _check_block_count,
    RequirementType.grid_size: _check_grid_size,
    RequirementType.pcu_limit: _check_pcu_limit,
    RequirementType.weapon_count: _check_weapon_count,
}
_BP_CHECKERS = {
    RequirementType.block_whitelist: _check_whitelist,
    RequirementType.block_blacklist: _check_blacklist,
}


@dataclass
class RequirementSpec:
    rule_type: RequirementType
    params: dict[str, Any]


def validate_blueprint(
    bp: ParsedBlueprint,
    requirements: list[RequirementSpec],
    lookup: BlockLookup,
) -> ValidationReport:
    stats = compute_stats(bp, lookup)
    results: list[RuleResult] = []

    # Unknown-block rule is always enforced first (hard fail).
    unknown = stats["unknown_blocks"]
    results.append(
        RuleResult(
            rule="unknown_blocks",
            param={},
            measured=unknown,
            allowed=[],
            passed=not unknown,
            detail=(
                "Unknown/modded blocks — ask an admin to update game data"
                if unknown
                else ""
            ),
        )
    )

    for req in requirements:
        if req.rule_type in _STATS_CHECKERS:
            results.append(_STATS_CHECKERS[req.rule_type](req.params, stats))
        elif req.rule_type in _BP_CHECKERS:
            results.append(_BP_CHECKERS[req.rule_type](req.params, bp))

    passed = all(r.passed for r in results)
    return ValidationReport(passed=passed, results=results, stats=stats)
