"""Artifact storage abstraction.

Primary backend is Backblaze B2 via its S3-compatible API (boto3). When B2 is
not configured we transparently fall back to a local filesystem store so the
app runs end-to-end in development. Both expose the same small interface:

    put(key, data, content_type) -> None
    get(key) -> bytes
    delete(key) -> None
    presigned_url(key, download_name) -> str
"""
from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod
from urllib.parse import quote

from app.core.config import settings


class Storage(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def presigned_url(self, key: str, download_name: str | None = None) -> str: ...


class LocalStorage(Storage):
    """Filesystem-backed store for local dev. Presigned URLs point at the API's
    ``/api/files`` passthrough route."""

    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def _path(self, key: str) -> str:
        safe = key.replace("..", "_")
        full = os.path.join(self.root, safe)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        return full

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        with open(self._path(key), "wb") as f:
            f.write(data)

    def get(self, key: str) -> bytes:
        with open(self._path(key), "rb") as f:
            return f.read()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)

    def presigned_url(self, key: str, download_name: str | None = None) -> str:
        url = f"/api/files/{quote(key)}"
        if download_name:
            url += f"?download={quote(download_name)}"
        return url

    def exists(self, key: str) -> bool:
        return os.path.exists(self._path(key))


class B2Storage(Storage):
    """Backblaze B2 via boto3 S3-compatible client."""

    def __init__(self):
        import boto3  # imported lazily so dev doesn't need the dep

        self.bucket = settings.b2_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.b2_endpoint_url,
            region_name=settings.b2_region,
            aws_access_key_id=settings.b2_key_id,
            aws_secret_access_key=settings.b2_application_key,
        )

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        resp = self.client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def presigned_url(self, key: str, download_name: str | None = None) -> str:
        params = {"Bucket": self.bucket, "Key": key}
        if download_name:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_name}"'
        return self.client.generate_presigned_url(
            "get_object", Params=params, ExpiresIn=settings.presigned_url_ttl_seconds
        )


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        if settings.b2_configured:
            _storage = B2Storage()
        else:
            _storage = LocalStorage(settings.local_storage_dir)
    return _storage
