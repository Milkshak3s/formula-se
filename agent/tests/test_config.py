import textwrap
from pathlib import Path

import pytest

from fse_agent.config import Config, ConfigError


def _write(tmp_path, body):
    p = Path(tmp_path) / "config.toml"
    p.write_text(textwrap.dedent(body))
    return p


def test_load_minimal(tmp_path, monkeypatch):
    monkeypatch.delenv("FSE_AGENT_TOKEN", raising=False)
    monkeypatch.delenv("FSE_AGENT_API_BASE_URL", raising=False)
    p = _write(
        tmp_path,
        """
        api_base_url = "https://fse.mlk.sh/"
        token = "fsa_abc"
        dry_run = true
        [se]
        saves_dir = "C:/saves"
        """,
    )
    cfg = Config.load(p)
    assert cfg.api_base_url == "https://fse.mlk.sh"  # trailing slash stripped
    assert cfg.token == "fsa_abc"
    assert cfg.dry_run is True
    assert cfg.se.saves_dir == Path("C:/saves")


def test_env_overrides_token(tmp_path, monkeypatch):
    monkeypatch.setenv("FSE_AGENT_TOKEN", "fsa_env")
    p = _write(
        tmp_path,
        """
        api_base_url = "https://x"
        token = "fsa_file"
        """,
    )
    cfg = Config.load(p)
    assert cfg.token == "fsa_env"  # env wins over file


def test_missing_token_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("FSE_AGENT_TOKEN", raising=False)
    p = _write(tmp_path, 'api_base_url = "https://x"\n')
    with pytest.raises(ConfigError):
        Config.load(p)


def test_validate_for_run_requires_se_paths(tmp_path, monkeypatch):
    monkeypatch.delenv("FSE_AGENT_TOKEN", raising=False)
    p = _write(
        tmp_path,
        """
        api_base_url = "https://x"
        token = "t"
        dry_run = false
        """,
    )
    cfg = Config.load(p)
    with pytest.raises(ConfigError):
        cfg.validate_for_run()


def test_validate_for_run_skipped_in_dry_run(tmp_path, monkeypatch):
    monkeypatch.delenv("FSE_AGENT_TOKEN", raising=False)
    p = _write(
        tmp_path,
        """
        api_base_url = "https://x"
        token = "t"
        dry_run = true
        """,
    )
    Config.load(p).validate_for_run()  # must not raise
