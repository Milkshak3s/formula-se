import pytest

from app.services.seformat.gps import parse_gps


def test_parse_gps_full():
    p = parse_gps("GPS:Start A:1024.5:-3.2:99999:#FF7500:")
    assert p.name == "Start A"
    assert p.x == 1024.5
    assert p.y == -3.2
    assert p.z == 99999
    assert p.color == "FF7500"


def test_parse_gps_no_color():
    p = parse_gps("GPS:Home:0:0:0:")
    assert (p.x, p.y, p.z) == (0, 0, 0)
    assert p.color is None


def test_parse_gps_invalid_prefix():
    with pytest.raises(ValueError):
        parse_gps("NOTGPS:x:1:2:3:")


def test_parse_gps_non_numeric():
    with pytest.raises(ValueError):
        parse_gps("GPS:Bad:a:b:c:")
