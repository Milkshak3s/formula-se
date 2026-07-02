"""Parse Space Engineers GPS strings.

Format: ``GPS:<Name>:<X>:<Y>:<Z>:#<Color>:`` where coordinates use ``.`` as the
decimal separator, e.g. ``GPS:Start A:1024.5:-3.2:99999:#FF7500:``.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedGps:
    name: str
    x: float
    y: float
    z: float
    color: str | None = None


def parse_gps(raw: str) -> ParsedGps:
    text = raw.strip()
    if not text.upper().startswith("GPS:"):
        raise ValueError("GPS string must start with 'GPS:'")

    # Split but tolerate a trailing colon and an optional color field.
    parts = text.split(":")
    # parts[0] == "GPS"
    if len(parts) < 5:
        raise ValueError("GPS string is missing coordinate fields")

    name = parts[1]
    try:
        x = float(parts[2])
        y = float(parts[3])
        z = float(parts[4])
    except ValueError as exc:  # noqa: PERF203
        raise ValueError(f"GPS coordinates are not numeric: {exc}") from exc

    color = None
    if len(parts) > 5 and parts[5]:
        color = parts[5].lstrip("#") or None

    return ParsedGps(name=name, x=x, y=y, z=z, color=color)
