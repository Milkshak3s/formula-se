import zipfile

from fse_agent.config import Config, SEControlConfig
from fse_agent.se_control import (
    WindowsSEController,
    _apply_cfg_values,
    world_folder_name,
)

CFG = (
    '<?xml version="1.0" encoding="utf-8"?>\r\n'
    '<MyConfigDedicated xmlns:xsd="http://www.w3.org/2001/XMLSchema"'
    ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\r\n'
    "  <LoadWorld>C:\\old\\World</LoadWorld>\r\n"
    "  <IgnoreLastSession>false</IgnoreLastSession>\r\n"
    "  <ServerName>My Server</ServerName>\r\n"
    "</MyConfigDedicated>\r\n"
)


def test_apply_updates_existing_tags():
    out = _apply_cfg_values(
        CFG, {"LoadWorld": "C:\\saves\\New", "IgnoreLastSession": "true"}
    )
    assert "<LoadWorld>C:\\saves\\New</LoadWorld>" in out
    assert "<IgnoreLastSession>true</IgnoreLastSession>" in out
    assert "<IgnoreLastSession>false</IgnoreLastSession>" not in out
    # Untouched fields + namespaces + CRLFs survive.
    assert "<ServerName>My Server</ServerName>" in out
    assert 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"' in out
    assert "\r\n" in out


def test_apply_inserts_missing_tag():
    no_ignore = CFG.replace(
        "  <IgnoreLastSession>false</IgnoreLastSession>\r\n", ""
    )
    out = _apply_cfg_values(no_ignore, {"IgnoreLastSession": "true"})
    assert "<IgnoreLastSession>true</IgnoreLastSession>" in out
    # Inserted inside the root element, before its close tag.
    assert out.index("<IgnoreLastSession>") < out.index("</MyConfigDedicated>")


def test_apply_handles_self_closing_tag():
    src = CFG.replace("<LoadWorld>C:\\old\\World</LoadWorld>", "<LoadWorld />")
    out = _apply_cfg_values(src, {"LoadWorld": "C:\\saves\\New"})
    assert "<LoadWorld>C:\\saves\\New</LoadWorld>" in out
    assert "<LoadWorld />" not in out


def _controller(tmp_path, ignore_last_session=True):
    cfg_file = tmp_path / "SpaceEngineers-Dedicated.cfg"
    cfg_file.write_bytes(CFG.encode("utf-8"))
    saves = tmp_path / "Saves"
    config = Config(
        api_base_url="x",
        token="t",
        se=SEControlConfig(
            saves_dir=saves,
            config_path=cfg_file,
            ignore_last_session=ignore_last_session,
        ),
    )
    return WindowsSEController(config), cfg_file, saves


def test_set_active_world_points_loadworld_and_forces_reload(tmp_path):
    ctrl, cfg_file, saves = _controller(tmp_path)
    ctrl.set_active_world("Match 1")
    out = cfg_file.read_text()
    assert f"<LoadWorld>{saves / 'Match 1'}</LoadWorld>" in out
    assert "<IgnoreLastSession>true</IgnoreLastSession>" in out


def test_set_active_world_respects_disabled_flag(tmp_path):
    ctrl, cfg_file, _ = _controller(tmp_path, ignore_last_session=False)
    ctrl.set_active_world("Match 1")
    out = cfg_file.read_text()
    # Left as the operator had it.
    assert "<IgnoreLastSession>false</IgnoreLastSession>" in out


def test_world_folder_name_reads_top_dir(tmp_path):
    zpath = tmp_path / "world.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("Match 1 — Finals/Sandbox.sbc", b"<x/>")
        zf.writestr("Match 1 — Finals/SANDBOX_0_0_0_.sbs", b"<x/>")
    assert world_folder_name(zpath) == "Match 1 — Finals"
