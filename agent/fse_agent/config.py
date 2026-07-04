"""Agent configuration: a TOML file plus a few environment overrides.

Pure stdlib — ``tomllib`` is built in on Python 3.11+ (``tomli`` is used as a
fallback on 3.10). Secrets (the token) and the API URL can be injected via the
environment so they needn't live in the file.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # py3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - only on 3.10
    import tomli as tomllib  # type: ignore

__all__ = ["AGENT_VERSION", "Config", "SEControlConfig", "ConfigError"]

AGENT_VERSION = "0.1.0"


class ConfigError(ValueError):
    pass


@dataclass
class SEControlConfig:
    # Where SE dedicated stores its worlds (…\SpaceEngineersDedicated\Instance\Saves).
    saves_dir: Path | None = None
    # The dedicated server config whose <LoadWorld> we point at the world folder.
    config_path: Path | None = None
    # Direct process management (used when no start_cmd is given).
    exe_path: Path | None = None
    exe_args: list[str] = field(default_factory=lambda: ["-console"])
    # Optional operator-provided overrides (Windows service, .bat, etc.).
    start_cmd: str | None = None
    stop_cmd: str | None = None
    process_name: str = "SpaceEngineersDedicated.exe"
    # When swapping worlds, also set <IgnoreLastSession>true</IgnoreLastSession>
    # so the server loads our world instead of resuming the last session.
    ignore_last_session: bool = True


@dataclass
class Config:
    api_base_url: str
    token: str
    poll_interval: float = 5.0
    dry_run: bool = False
    verify_tls: bool = True
    state_file: Path = Path("fse-agent-state.json")
    download_dir: Path = Path("fse-agent-downloads")
    se: SEControlConfig = field(default_factory=SEControlConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "Config":
        data = dict(data or {})
        se_raw = dict(data.pop("se", {}) or {})

        # Environment wins over the file for the two things you most want to keep
        # out of a checked-in config: the base URL and the secret token.
        api_base_url = os.environ.get("FSE_AGENT_API_BASE_URL", data.get("api_base_url"))
        token = os.environ.get("FSE_AGENT_TOKEN", data.get("token"))
        dry_env = os.environ.get("FSE_AGENT_DRY_RUN")
        dry_run = _as_bool(dry_env) if dry_env is not None else bool(data.get("dry_run", False))

        if not api_base_url:
            raise ConfigError("api_base_url is required (config or FSE_AGENT_API_BASE_URL)")
        if not token:
            raise ConfigError("token is required (config or FSE_AGENT_TOKEN)")

        se = SEControlConfig(
            saves_dir=_as_path(se_raw.get("saves_dir")),
            config_path=_as_path(se_raw.get("config_path")),
            exe_path=_as_path(se_raw.get("exe_path")),
            exe_args=list(se_raw.get("exe_args", ["-console"])),
            start_cmd=se_raw.get("start_cmd"),
            stop_cmd=se_raw.get("stop_cmd"),
            process_name=se_raw.get("process_name", "SpaceEngineersDedicated.exe"),
            ignore_last_session=bool(se_raw.get("ignore_last_session", True)),
        )
        return cls(
            api_base_url=str(api_base_url).rstrip("/"),
            token=str(token),
            poll_interval=float(data.get("poll_interval", 5.0)),
            dry_run=dry_run,
            verify_tls=bool(data.get("verify_tls", True)),
            state_file=_as_path(data.get("state_file")) or Path("fse-agent-state.json"),
            download_dir=_as_path(data.get("download_dir")) or Path("fse-agent-downloads"),
            se=se,
        )

    @classmethod
    def load(cls, path) -> "Config":
        p = Path(path)
        if not p.exists():
            raise ConfigError(f"config file not found: {p}")
        with open(p, "rb") as f:
            data = tomllib.load(f)
        return cls.from_dict(data)

    def validate_for_run(self) -> None:
        """Extra checks required for a real (non-dry-run) SE deployment."""
        if self.dry_run:
            return
        missing = []
        if self.se.saves_dir is None:
            missing.append("se.saves_dir")
        if self.se.config_path is None:
            missing.append("se.config_path")
        if self.se.exe_path is None and self.se.start_cmd is None:
            missing.append("se.exe_path or se.start_cmd")
        if missing:
            raise ConfigError(
                "missing SE control config for a live run: " + ", ".join(missing)
            )


def _as_bool(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _as_path(v):
    return Path(v) if v else None
