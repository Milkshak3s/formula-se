"""Local-storage passthrough for presigned URLs in dev (no B2 configured).

In production with B2, ``presigned_url`` returns a direct B2 URL and these
routes are never hit.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.services.storage import LocalStorage, get_storage

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{key:path}")
def get_file(key: str, download: str | None = Query(default=None)):
    storage = get_storage()
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Direct file access unavailable")
    try:
        data = storage.get(key)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found") from exc

    headers = {}
    media_type = "application/octet-stream"
    if key.endswith(".png"):
        media_type = "image/png"
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{download}"'
    return Response(content=data, media_type=media_type, headers=headers)
