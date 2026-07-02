"""World delivery abstraction (PLAN §3.5).

MVP ships only the no-op ``DownloadDeliverer`` — prepared worlds are always
downloadable as a zip. The concrete push transport is **deferred**: the plan is a
separate SE client app that polls for world starts, so this app does not push to
a dedicated server itself. A concrete :class:`WorldDeliverer` implementation can
be added later behind the ``server_push_enabled`` feature flag if needed.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeliveryResult:
    delivered: bool
    detail: str


class WorldDeliverer(ABC):
    @abstractmethod
    def deliver(self, prepared_world_id: str, b2_key: str) -> DeliveryResult: ...


class DownloadDeliverer(WorldDeliverer):
    """The guaranteed MVP path: nothing to push, download is always available."""

    def deliver(self, prepared_world_id: str, b2_key: str) -> DeliveryResult:
        return DeliveryResult(
            delivered=True,
            detail="Prepared world is available for download.",
        )


def get_deliverer() -> WorldDeliverer:
    # Only the download deliverer is wired up in the MVP.
    return DownloadDeliverer()
