"""Controlling the Space Engineers dedicated server (best-effort, Windows).

The reconcile loop orchestrates four steps: ``stop`` → ``install_world`` →
``set_active_world`` → ``start``. The interface is abstract so the loop can be
unit-tested with a fake, and so a ``DryRunController`` can exercise the whole
pipeline without touching a real install.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path

from .config import Config

log = logging.getLogger("fse_agent.se")

__all__ = ["ServerController", "DryRunController", "WindowsSEController", "make_controller"]


def world_folder_name(zip_path) -> str:
    """Top-level folder inside a prepared-world zip (the SE save folder name)."""
    with zipfile.ZipFile(zip_path) as zf:
        tops = {n.split("/", 1)[0] for n in zf.namelist() if n.strip("/")}
    if len(tops) != 1:
        # Not cleanly single-rooted — fall back to the archive stem.
        return Path(zip_path).stem
    return next(iter(tops))


class ServerController(ABC):
    @abstractmethod
    def is_running(self) -> bool: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def install_world(self, zip_path) -> str:
        """Extract the world into the Saves dir; return its folder name."""

    @abstractmethod
    def set_active_world(self, folder_name: str) -> None: ...

    @abstractmethod
    def start(self) -> None: ...


class DryRunController(ServerController):
    """Logs every action and tracks in-memory state; touches nothing on disk."""

    def __init__(self):
        self._running = False
        self._world: str | None = None

    def is_running(self) -> bool:
        return self._running

    def stop(self) -> None:
        log.info("[dry-run] stop server")
        self._running = False

    def install_world(self, zip_path) -> str:
        name = world_folder_name(zip_path)
        log.info("[dry-run] install world '%s' from %s", name, zip_path)
        self._world = name
        return name

    def set_active_world(self, folder_name: str) -> None:
        log.info("[dry-run] point <LoadWorld> at '%s'", folder_name)

    def start(self) -> None:
        log.info("[dry-run] start server (world=%s)", self._world)
        self._running = True


class WindowsSEController(ServerController):
    """Manages a real dedicated server via its process/config/save folder."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.se = cfg.se
        self._proc: subprocess.Popen | None = None

    def is_running(self) -> bool:
        if self._proc is not None and self._proc.poll() is None:
            return True
        # Survive agent restarts by also checking for the process by name.
        return _process_running(self.se.process_name)

    def stop(self) -> None:
        if self.se.stop_cmd:
            log.info("stop: running stop_cmd")
            _run(self.se.stop_cmd)
            self._proc = None
            return
        if self._proc is not None and self._proc.poll() is None:
            log.info("stop: terminating tracked process")
            self._proc.terminate()
            try:
                self._proc.wait(timeout=30)
            except Exception:
                self._proc.kill()
            self._proc = None
            return
        _taskkill(self.se.process_name)

    def install_world(self, zip_path) -> str:
        assert self.se.saves_dir is not None
        name = world_folder_name(zip_path)
        dest = Path(self.se.saves_dir) / name
        # Replace any prior copy so a re-run is a clean install, not a merge.
        if dest.exists():
            shutil.rmtree(dest)
        Path(self.se.saves_dir).mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(self.se.saves_dir)
        log.info("installed world '%s' into %s", name, self.se.saves_dir)
        return name

    def set_active_world(self, folder_name: str) -> None:
        assert self.se.saves_dir is not None and self.se.config_path is not None
        world_path = str(Path(self.se.saves_dir) / folder_name)
        _set_load_world(Path(self.se.config_path), world_path)
        log.info("set <LoadWorld> -> %s", world_path)

    def start(self) -> None:
        if self.se.start_cmd:
            log.info("start: running start_cmd")
            self._proc = _popen(self.se.start_cmd, shell=True)
            return
        assert self.se.exe_path is not None
        log.info("start: launching %s %s", self.se.exe_path, " ".join(self.se.exe_args))
        self._proc = _popen([str(self.se.exe_path), *self.se.exe_args])


def _set_load_world(config_path: Path, world_path: str) -> None:
    """Point the dedicated config's <LoadWorld> element at ``world_path``."""
    tree = ET.parse(config_path)
    root = tree.getroot()
    el = root.find("LoadWorld")
    if el is None:
        el = ET.SubElement(root, "LoadWorld")
    el.text = world_path
    tree.write(config_path, encoding="utf-8", xml_declaration=True)


def _process_running(name: str) -> bool:
    if os.name != "nt":
        return False
    try:
        out = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}"],
            capture_output=True,
            text=True,
        )
        return name.lower() in out.stdout.lower()
    except Exception:  # pragma: no cover - defensive
        return False


def _taskkill(name: str) -> None:
    if os.name != "nt":
        log.info("stop: no tracked process and not on Windows; nothing to kill")
        return
    subprocess.run(["taskkill", "/IM", name, "/F"], capture_output=True)


def _run(cmd: str) -> None:
    subprocess.run(cmd, shell=True, check=False)


def _popen(cmd, shell: bool = False) -> subprocess.Popen:
    return subprocess.Popen(cmd, shell=shell)


def make_controller(cfg: Config) -> ServerController:
    return DryRunController() if cfg.dry_run else WindowsSEController(cfg)
