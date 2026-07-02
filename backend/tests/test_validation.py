from app.models.enums import RequirementType
from app.services.seformat.blueprint import parse_blueprint
from app.services.validation.engine import (
    BlockDef,
    DictBlockLookup,
    RequirementSpec,
    validate_blueprint,
)
from tests.fixtures import make_blueprint_xml

DEFS = [
    BlockDef("Cockpit", "LargeBlockCockpit", pcu=15, is_weapon=False, grid_size="Large"),
    BlockDef("Reactor", "LargeBlockLargeGenerator", pcu=25, is_weapon=False, grid_size="Large"),
    BlockDef("Gyro", "LargeBlockGyro", pcu=10, is_weapon=False, grid_size="Large"),
    BlockDef("Thrust", "LargeBlockLargeThrust", pcu=5, is_weapon=False, grid_size="Large"),
    BlockDef("LargeMissileTurret", "LargeCalibreTurret", pcu=160, is_weapon=True, grid_size="Large"),
]
LOOKUP = DictBlockLookup(DEFS)


def _bp(**kw):
    return parse_blueprint(make_blueprint_xml(**kw))


def test_all_pass_no_rules():
    report = validate_blueprint(_bp(), [], LOOKUP)
    assert report.passed
    assert report.stats["pcu"] == 55
    assert report.stats["weapon_count"] == 0


def test_unknown_block_hard_fails():
    bp = _bp(blocks=[("ModBlock", "SomethingWeird")])
    report = validate_blueprint(bp, [], LOOKUP)
    assert not report.passed
    unknown = next(r for r in report.results if r.rule == "unknown_blocks")
    assert unknown.measured == ["ModBlock/SomethingWeird"]


def test_pcu_limit():
    specs = [RequirementSpec(RequirementType.pcu_limit, {"max": 50})]
    assert not validate_blueprint(_bp(), specs, LOOKUP).passed
    specs = [RequirementSpec(RequirementType.pcu_limit, {"max": 100})]
    assert validate_blueprint(_bp(), specs, LOOKUP).passed


def test_block_count():
    specs = [RequirementSpec(RequirementType.block_count, {"min": 2, "max": 3})]
    assert not validate_blueprint(_bp(), specs, LOOKUP).passed  # 4 blocks > 3
    specs = [RequirementSpec(RequirementType.block_count, {"min": 2, "max": 10})]
    assert validate_blueprint(_bp(), specs, LOOKUP).passed


def test_grid_size():
    specs = [RequirementSpec(RequirementType.grid_size, {"size": "Small"})]
    assert not validate_blueprint(_bp(), specs, LOOKUP).passed
    specs = [RequirementSpec(RequirementType.grid_size, {"size": "Large"})]
    assert validate_blueprint(_bp(), specs, LOOKUP).passed


def test_weapon_count():
    weaponized = _bp(
        blocks=[
            ("Cockpit", "LargeBlockCockpit"),
            ("LargeMissileTurret", "LargeCalibreTurret"),
            ("LargeMissileTurret", "LargeCalibreTurret"),
        ]
    )
    specs = [RequirementSpec(RequirementType.weapon_count, {"max": 1})]
    report = validate_blueprint(weaponized, specs, LOOKUP)
    assert not report.passed
    assert report.stats["weapon_count"] == 2


def test_blacklist_cap():
    bp = _bp(
        blocks=[("Gyro", "LargeBlockGyro"), ("Gyro", "LargeBlockGyro"), ("Gyro", "LargeBlockGyro")]
    )
    specs = [
        RequirementSpec(
            RequirementType.block_blacklist,
            {"rules": [{"subtype_id": "LargeBlockGyro", "max": 2}]},
        )
    ]
    assert not validate_blueprint(bp, specs, LOOKUP).passed


def test_whitelist():
    specs = [
        RequirementSpec(
            RequirementType.block_whitelist,
            {"type_ids": ["Cockpit", "Reactor", "Gyro"], "subtype_ids": []},
        )
    ]
    # Default bp includes Thrust which is not whitelisted → fail
    assert not validate_blueprint(_bp(), specs, LOOKUP).passed
