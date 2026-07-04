from pathlib import Path

from fse_agent.agent import AgentState, reconcile_once


class FakeController:
    def __init__(self, running=False):
        self.running = running
        self.calls: list = []
        self.fail_on: str | None = None

    def is_running(self):
        return self.running

    def stop(self):
        self.calls.append("stop")
        self.running = False
        if self.fail_on == "stop":
            raise RuntimeError("stop boom")

    def install_world(self, zip_path):
        self.calls.append(("install", str(zip_path)))
        if self.fail_on == "install":
            raise RuntimeError("install boom")
        return "MyWorld"

    def set_active_world(self, folder):
        self.calls.append(("set_active", folder))

    def start(self):
        self.calls.append("start")
        self.running = True
        if self.fail_on == "start":
            raise RuntimeError("start boom")


RUN = {
    "action": "run",
    "prepared_world": {"id": "w1", "name": "W1", "download_url": "http://x/w1.zip"},
}
STOP = {"action": "stop", "prepared_world": None}


def _run(desired, state, controller, tmp_path):
    statuses: list = []
    downloads: list = []

    def on_status(s, wid, err):
        statuses.append((s, wid, err))

    def download(url, dest):
        downloads.append((url, str(dest)))

    reconcile_once(desired, state, controller, download, tmp_path, on_status)
    return statuses, downloads


def test_run_new_world_deploys(tmp_path):
    state = AgentState()
    ctrl = FakeController(running=False)
    statuses, downloads = _run(RUN, state, ctrl, tmp_path)

    assert [s for s, _, _ in statuses] == ["starting", "running"]
    # Full deploy sequence, in order.
    assert ctrl.calls == [
        "stop",
        ("install", str(Path(tmp_path) / "w1.zip")),
        ("set_active", "MyWorld"),
        "start",
    ]
    assert downloads == [("http://x/w1.zip", str(Path(tmp_path) / "w1.zip"))]
    assert state.current_world_id == "w1"


def test_run_same_world_already_running_is_noop(tmp_path):
    state = AgentState(current_world_id="w1")
    ctrl = FakeController(running=True)
    statuses, downloads = _run(RUN, state, ctrl, tmp_path)

    assert [s for s, _, _ in statuses] == ["running"]
    assert ctrl.calls == []
    assert downloads == []
    assert state.current_world_id == "w1"


def test_run_same_world_but_crashed_redeploys(tmp_path):
    # State says w1 but the process isn't actually up → redeploy, self-healing.
    state = AgentState(current_world_id="w1")
    ctrl = FakeController(running=False)
    statuses, downloads = _run(RUN, state, ctrl, tmp_path)

    assert [s for s, _, _ in statuses] == ["starting", "running"]
    assert "start" in ctrl.calls
    assert downloads  # it downloaded again


def test_stop_when_running(tmp_path):
    state = AgentState(current_world_id="w1")
    ctrl = FakeController(running=True)
    statuses, _ = _run(STOP, state, ctrl, tmp_path)

    assert statuses[-1] == ("idle", None, None)
    assert "stop" in ctrl.calls
    assert state.current_world_id is None


def test_stop_when_idle_is_noop(tmp_path):
    state = AgentState()
    ctrl = FakeController(running=False)
    statuses, _ = _run(STOP, state, ctrl, tmp_path)

    assert statuses == [("idle", None, None)]
    assert ctrl.calls == []


def test_deploy_error_reports_error_and_does_not_mark_running(tmp_path):
    state = AgentState(current_world_id=None)
    ctrl = FakeController(running=False)
    ctrl.fail_on = "start"
    statuses, _ = _run(RUN, state, ctrl, tmp_path)

    assert statuses[0][0] == "starting"
    assert statuses[-1][0] == "error"
    assert "boom" in statuses[-1][2]
    assert state.current_world_id is None


def test_run_order_missing_url_is_error(tmp_path):
    state = AgentState()
    ctrl = FakeController(running=False)
    bad = {"action": "run", "prepared_world": {"id": "w1"}}  # no download_url
    statuses, _ = _run(bad, state, ctrl, tmp_path)

    assert statuses[-1][0] == "error"
    assert ctrl.calls == []
