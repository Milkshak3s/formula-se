"""Pure helpers for the server-agent reconciliation loop.

Kept free of DB/IO so they're trivially unit-testable, matching the repo's
services-are-pure convention.
"""
from __future__ import annotations

from datetime import datetime, timezone

# An agent that hasn't polled within this many seconds is considered offline.
# Comfortably larger than DEFAULT_POLL_INTERVAL_SECONDS so a single slow poll
# doesn't flap the status.
SERVER_ONLINE_TIMEOUT_SECONDS = 30
# How often the agent is told to poll.
DEFAULT_POLL_INTERVAL_SECONDS = 5

# States an agent may legitimately report.
AGENT_STATES = {"offline", "idle", "starting", "running", "error"}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def is_online(
    last_seen_at: datetime | None,
    now: datetime | None = None,
    timeout_seconds: int = SERVER_ONLINE_TIMEOUT_SECONDS,
) -> bool:
    """True if the agent's last heartbeat is recent enough."""
    if last_seen_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    return (_aware(now) - _aware(last_seen_at)).total_seconds() <= timeout_seconds


def absolutize_url(url: str, base_url: str) -> str:
    """Make a possibly-relative storage URL absolute for an out-of-browser agent.

    ``LocalStorage`` hands out relative ``/api/files/...`` URLs; B2 returns
    absolute ones already. The agent isn't a browser, so a relative URL is
    useless to it — anchor it on the request base URL.
    """
    if url.startswith(("http://", "https://")):
        return url
    return base_url.rstrip("/") + "/" + url.lstrip("/")


def normalize_reported_state(state: str | None) -> str:
    """Coerce an agent-reported state to a known value (defaults to ``idle``)."""
    s = (state or "").strip().lower()
    return s if s in AGENT_STATES else "idle"
