"""World delivery abstraction (PLAN §3.5).

The guaranteed MVP path is download — prepared worlds are always downloadable as
a zip via a presigned/passthrough URL. Optionally, when the ``server_push``
feature flag is on and ``DELIVERER=sftp`` is configured, a prepared world can
additionally be **pushed** to a dedicated server's saves directory over SFTP.

Both implement the same :class:`WorldDeliverer` interface so the transport is
swappable (panel API / Torch could be added the same way).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.config import settings
from app.services.storage import get_storage


@dataclass
class DeliveryResult:
    delivered: bool
    detail: str


class WorldDeliverer(ABC):
    @abstractmethod
    def deliver(self, prepared_world_id: str, b2_key: str, filename: str) -> DeliveryResult: ...


class DownloadDeliverer(WorldDeliverer):
    """The guaranteed MVP path: nothing to push, download is always available."""

    def deliver(self, prepared_world_id: str, b2_key: str, filename: str) -> DeliveryResult:
        return DeliveryResult(
            delivered=True,
            detail="Prepared world is available for download.",
        )


class SftpDeliverer(WorldDeliverer):
    """Push the prepared-world zip to a dedicated server over SFTP.

    ``paramiko`` is imported lazily so it's only required when this transport is
    actually used (it's an optional, feature-flagged dependency).
    """

    def deliver(self, prepared_world_id: str, b2_key: str, filename: str) -> DeliveryResult:
        if not settings.sftp_host or not settings.sftp_username:
            return DeliveryResult(False, "SFTP host/username are not configured.")

        try:
            import paramiko
        except ImportError:
            return DeliveryResult(
                False, "paramiko is not installed; cannot push over SFTP."
            )

        data = get_storage().get(b2_key)

        transport = paramiko.Transport((settings.sftp_host, settings.sftp_port))
        try:
            transport.connect(
                username=settings.sftp_username, password=settings.sftp_password
            )
            sftp = paramiko.SFTPClient.from_transport(transport)
            assert sftp is not None
            remote_dir = settings.sftp_remote_dir.rstrip("/")
            _ensure_remote_dir(sftp, remote_dir)
            remote_path = f"{remote_dir}/{_safe_name(filename)}"
            import io

            sftp.putfo(io.BytesIO(data), remote_path)
            sftp.close()
        except Exception as exc:  # noqa: BLE001 — report transport failures to caller
            return DeliveryResult(False, f"SFTP push failed: {exc}")
        finally:
            transport.close()

        return DeliveryResult(True, f"Pushed to {settings.sftp_host}:{remote_path}")


def _ensure_remote_dir(sftp, path: str) -> None:
    parts = [p for p in path.split("/") if p]
    cur = ""
    for p in parts:
        cur = f"{cur}/{p}"
        try:
            sftp.stat(cur)
        except IOError:
            sftp.mkdir(cur)


def _safe_name(name: str) -> str:
    keep = [c if c.isalnum() or c in " -_." else "_" for c in name.strip()]
    cleaned = "".join(keep).strip() or "prepared_world.zip"
    return cleaned if cleaned.lower().endswith(".zip") else f"{cleaned}.zip"


def get_deliverer() -> WorldDeliverer:
    if settings.deliverer.lower() == "sftp":
        return SftpDeliverer()
    return DownloadDeliverer()
