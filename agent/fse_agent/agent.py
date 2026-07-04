"""The reconcile loop: poll → converge on desired state → report."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from .client import ApiClient, ApiError
from .config import AGENT_VERSION, Config
from .se_control import ServerController

log = logging.getLogger("fse_agent")

__all__ = ["Agent", "AgentState", "reconcile_once", "load_state", "save_state"]


@dataclass
class AgentState:
    # The prepared world we believe is installed + running.
    current_world_id: str | None = None


def load_state(path) -> AgentState:
    p = Path(path)
    if p.exists():
        try:
            data = json.loads(p.read_text())
            return AgentState(current_world_id=data.get("current_world_id"))
        except Exception:
            log.warning("could not read state file %s; starting fresh", p)
    return AgentState()


def save_state(path, state: AgentState) -> None:
    Path(path).write_text(json.dumps({"current_world_id": state.current_world_id}))


def reconcile_once(desired, state, controller, download_world, download_dir, on_status) -> AgentState:
    """Converge on one poll's ``desired`` state (pure orchestration, testable).

    ``on_status(state_str, world_id, error)`` is invoked at each transition so the
    caller can push interim heartbeats (e.g. ``starting`` before the blocking
    deploy) and record the final outcome. Any failure is caught and surfaced as an
    ``error`` status without crashing the loop.
    """
    action = (desired or {}).get("action", "stop")

    if action == "run":
        world = (desired or {}).get("prepared_world") or {}
        wid = world.get("id")
        url = world.get("download_url")
        if not wid or not url:
            on_status("error", state.current_world_id, "run order missing world id / url")
            return state

        if state.current_world_id == wid and controller.is_running():
            on_status("running", wid, None)  # already converged
            return state

        on_status("starting", wid, None)
        try:
            controller.stop()
            zip_path = Path(download_dir) / f"{wid}.zip"
            download_world(url, zip_path)
            folder = controller.install_world(zip_path)
            controller.set_active_world(folder)
            controller.start()
        except Exception as e:  # noqa: BLE001 - report any failure, keep looping
            on_status("error", state.current_world_id, str(e))
            return state

        state.current_world_id = wid
        on_status("running", wid, None)
        return state

    # action == "stop" (default): shut down if we're running anything.
    if state.current_world_id is not None or controller.is_running():
        try:
            controller.stop()
        except Exception as e:  # noqa: BLE001
            on_status("error", state.current_world_id, str(e))
            return state
        state.current_world_id = None
    on_status("idle", None, None)
    return state


class Agent:
    def __init__(self, config: Config, client: ApiClient, controller: ServerController):
        self.config = config
        self.client = client
        self.controller = controller
        self.state = load_state(config.state_file)
        self.reported_state = "running" if self.state.current_world_id else "idle"
        self.error: str | None = None

    def _report(self, state_str: str, world_id: str | None, error: str | None) -> dict:
        return self.client.poll(
            {
                "state": state_str,
                "prepared_world_id": world_id,
                "error": error,
                "agent_version": AGENT_VERSION,
            }
        )

    def _on_status(self, state_str: str, world_id: str | None, error: str | None) -> None:
        self.reported_state = state_str
        self.error = error
        # Push an interim heartbeat so the UI reflects transitions promptly; the
        # desired state it returns is ignored — the main loop drives reconciliation.
        try:
            self._report(state_str, world_id, error)
        except ApiError as e:
            log.warning("status heartbeat failed: %s", e)

    def tick(self) -> float:
        resp = self._report(self.reported_state, self.state.current_world_id, self.error)
        interval = float(resp.get("poll_interval_seconds") or self.config.poll_interval)
        desired = resp.get("desired") or {"action": "stop"}
        reconcile_once(
            desired,
            self.state,
            self.controller,
            self.client.download,
            self.config.download_dir,
            self._on_status,
        )
        save_state(self.config.state_file, self.state)
        return interval

    def run(self) -> None:
        log.info(
            "fse-agent %s starting; polling %s (dry_run=%s)",
            AGENT_VERSION,
            self.config.api_base_url,
            self.config.dry_run,
        )
        while True:
            try:
                interval = self.tick()
            except ApiError as e:
                log.warning("poll failed: %s", e)
                interval = self.config.poll_interval
            time.sleep(max(1.0, interval))
