from app.services.seformat.blueprint import (
    extract_bp_sbc,
    extract_grids_xml,
    extract_thumbnail,
    parse_blueprint,
)
from tests.fixtures import make_blueprint_xml, make_blueprint_zip


def test_parse_raw_xml():
    bp = parse_blueprint(make_blueprint_xml())
    assert bp.display_name == "Test Ship"
    assert bp.block_count == 4
    assert bp.grid_sizes == {"Large"}
    assert len(bp.grids) == 1


def test_block_type_counts():
    bp = parse_blueprint(
        make_blueprint_xml(
            blocks=[("Gyro", "LargeBlockGyro"), ("Gyro", "LargeBlockGyro")]
        )
    )
    counts = bp.block_type_counts()
    assert counts[("Gyro", "LargeBlockGyro")] == 2


def test_extract_from_zip_and_thumbnail():
    z = make_blueprint_zip()
    bp_sbc = extract_bp_sbc(z, "MyShip.zip")
    bp = parse_blueprint(bp_sbc)
    assert bp.display_name == "Test Ship"
    thumb = extract_thumbnail(z)
    assert thumb is not None and thumb.startswith(b"\x89PNG")


def test_extract_grids_xml():
    grids = extract_grids_xml(make_blueprint_xml())
    assert b"CubeGrid" in grids
    assert b"CubeGrids" in grids
