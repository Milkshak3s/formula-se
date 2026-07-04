# Formula SE — server agent

A small agent that runs on the **Windows host** next to a Space Engineers
dedicated server. It polls the Formula SE API and, when a commander clicks
**Start** on a prepared world in the web UI, downloads that world and (re)starts
the dedicated server on it. Clicking **Stop** shuts it down.

It is a **reconcile loop**, not a fire-and-forget queue: each poll compares the
*desired* world (from the app) with what's *actually* running and converges — so
an agent restart is self-healing, and the web UI shows live per-server status.

Pure Python standard library (no third-party dependencies on Python 3.11+).

## How it works

Each cycle the agent POSTs its status to `/api/agent/poll` (bearer-token auth)
and gets back a desired state:

- **run `<world>`** → if it isn't already the running world: stop the server,
  download the world zip, extract it into the dedicated `Saves` dir, point the
  dedicated config's `<LoadWorld>` at it, and start the server.
- **stop** → shut the server down.

Progress (`starting` → `running`, or `error`) is reported straight back, so the
Prepared Worlds page reflects it within a few seconds.

## Prerequisites

- Python **3.11+** on the host (or build the standalone `.exe`, below).
- A server registered in the web UI: **Admin → Dedicated servers → Register**.
  Copy the token it shows **once**.
- **Settings → Enable dedicated-server push** turned on (Start/Stop is gated on
  this flag).

## Configure

```powershell
copy config.example.toml config.toml
notepad config.toml          # set api_base_url and the [se] paths
$env:FSE_AGENT_TOKEN = "fsa_..."   # keep the secret out of the file (env wins)
```

Key `[se]` settings (see `config.example.toml` for the full list):

| setting | meaning |
| --- | --- |
| `saves_dir` | dedicated instance `…\Saves` — worlds are extracted here |
| `config_path` | `SpaceEngineers-Dedicated.cfg` whose `<LoadWorld>` is repointed |
| `exe_path` / `exe_args` | manage `SpaceEngineersDedicated.exe` directly |
| `start_cmd` / `stop_cmd` | *override* with your own commands (service, `.bat`, NSSM) |

## Run

```powershell
python -m fse_agent -c config.toml          # or: fse-agent -c config.toml
python -m fse_agent -c config.toml -v        # debug logging
```

### Dry run (no SE required)

Set `dry_run = true` (or `FSE_AGENT_DRY_RUN=1`). The agent performs the full
pipeline — poll, download, "start" — but only **logs** the SE actions and never
touches a real install. Use it to validate connectivity and the Start/Stop flow
end to end before pointing it at a live server.

## Build a standalone `fse-agent.exe`

So operators don't need Python installed:

```powershell
pip install pyinstaller
pyinstaller --onefile --name fse-agent fse_agent/__main__.py
# → dist\fse-agent.exe ;  run:  fse-agent.exe -c config.toml
```

## Run as a Windows service

Use any process supervisor; [NSSM](https://nssm.cc) is simplest:

```powershell
nssm install FSEAgent "C:\fse-agent\fse-agent.exe" "-c" "C:\fse-agent\config.toml"
nssm set FSEAgent AppEnvironmentExtra FSE_AGENT_TOKEN=fsa_...
nssm start FSEAgent
```

(A Scheduled Task set to "run at startup / restart on failure" works too.)

## Security notes

- The token is a bearer credential for **this one server**; the app stores only
  its SHA-256 digest. If it leaks, rotate it in the UI (**Rotate token**) — the
  old one stops working immediately.
- Prefer `FSE_AGENT_TOKEN` over putting the token in `config.toml`.
- Keep `verify_tls = true` for `https://` endpoints.

## Tests

```bash
pip install pytest
pytest            # reconcile loop + config parsing
```
