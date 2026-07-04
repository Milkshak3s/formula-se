"""Tiny HTTP client for the Formula SE agent API (stdlib urllib, no deps)."""
from __future__ import annotations

import json
import shutil
import ssl
import urllib.error
import urllib.request
from pathlib import Path

__all__ = ["ApiClient", "ApiError"]


class ApiError(Exception):
    pass


class ApiClient:
    def __init__(self, base_url: str, token: str, verify_tls: bool = True, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        # Only relax verification if explicitly asked (self-signed dev endpoints).
        self._ctx = None if verify_tls else ssl._create_unverified_context()

    def poll(self, report: dict) -> dict:
        """POST the agent's status report, return the server's desired state."""
        body = json.dumps(report).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/api/agent/poll",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.token}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            raise ApiError(f"poll failed: HTTP {e.code} {detail}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ApiError(f"poll failed: {e}") from e

    def download(self, url: str, dest) -> None:
        """Stream a world archive to ``dest``.

        The URL is a presigned/absolute link (B2) or the app's public files route
        (local dev); neither needs the agent's Authorization header.
        """
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self._ctx) as resp, open(
                dest, "wb"
            ) as f:
                shutil.copyfileobj(resp, f)
        except urllib.error.HTTPError as e:
            raise ApiError(f"download failed: HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ApiError(f"download failed: {e}") from e
