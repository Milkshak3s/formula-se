"""Enumerations shared across models and schemas."""
from __future__ import annotations

import enum


class Role(str, enum.Enum):
    """Strict role hierarchy: admin ⊃ commander ⊃ engineer ⊃ member.

    Ordering (via ``level``) powers ``require_role`` authorization checks.
    """

    member = "member"
    engineer = "engineer"
    commander = "commander"
    admin = "admin"

    @property
    def level(self) -> int:
        return _ROLE_ORDER[self]

    def satisfies(self, required: "Role") -> bool:
        """True if this role is at least as privileged as ``required``."""
        return self.level >= required.level


_ROLE_ORDER: dict[Role, int] = {
    Role.member: 0,
    Role.engineer: 1,
    Role.commander: 2,
    Role.admin: 3,
}


class RequirementType(str, enum.Enum):
    block_count = "block_count"      # params: {min?: int, max?: int}
    grid_size = "grid_size"          # params: {size: "Large"|"Small"}
    pcu_limit = "pcu_limit"          # params: {max: int}
    weapon_count = "weapon_count"    # params: {max: int}
    block_whitelist = "block_whitelist"  # params: {type_ids: [...], subtype_ids: [...]}
    block_blacklist = "block_blacklist"  # params: {rules: [{type_id?, subtype_id?, max: int}]}


class GridSize(str, enum.Enum):
    large = "Large"
    small = "Small"


class BlueprintStatus(str, enum.Enum):
    active = "active"
    replaced = "replaced"
    cleared = "cleared"


class PreparedWorldStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"
    expired = "expired"


class HexTerrain(str, enum.Enum):
    """Flavour/terrain of a sector-map hex.

    Cosmetic today; the natural anchor for future gameplay (resource yields,
    where stations may be built, movement cost). ``deep_space`` is the empty
    default; ``star_system`` marks the campaign's home sector at the origin.
    """

    deep_space = "deep_space"
    asteroid_field = "asteroid_field"
    nebula = "nebula"
    ice_field = "ice_field"
    planet = "planet"
    star_system = "star_system"
