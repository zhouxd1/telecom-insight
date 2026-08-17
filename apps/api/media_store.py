"""Safe save/serve helpers for org branding uploads."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

ALLOWED = {".png": b"\x89PNG", ".webp": b"RIFF", ".svg": None}  # svg: content-type + sanitize
MAX_BYTES = 512_000
_KINDS = frozenset({"logo", "favicon"})
MEDIA_TYPES = {
    ".png": "image/png",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}
_SVG_OK_TYPES = frozenset({"image/svg+xml", "text/xml", "application/xml"})
# Event handlers like onload / onerror (word-boundary style).
_SVG_EVENT_RE = re.compile(r"\bon[a-z]+\s*=", re.IGNORECASE)
_SVG_JS_URL_RE = re.compile(r"javascript\s*:", re.IGNORECASE)


class MediaStoreError(ValueError):
    """Invalid branding upload or path."""


# Alias for callers that prefer branding-specific naming
BrandingMediaError = MediaStoreError


def media_content_type(filename: str) -> str:
    return MEDIA_TYPES.get(Path(filename).suffix.lower(), "application/octet-stream")


async def read_upload_capped(upload: Any, *, max_bytes: int = MAX_BYTES) -> bytes:
    """Read an UploadFile-like object with a hard size cap (never buffer past max+1)."""
    headers = getattr(upload, "headers", None) or {}
    cl = headers.get("content-length") or headers.get("Content-Length")
    if cl is None:
        size = getattr(upload, "size", None)
        if size is not None:
            cl = str(size)
    if cl is not None:
        try:
            declared = int(cl)
        except (TypeError, ValueError) as exc:
            raise MediaStoreError("invalid content length") from exc
        if declared > max_bytes:
            raise MediaStoreError("file too large")

    chunks: list[bytes] = []
    total = 0
    while True:
        # Read in bounded chunks; stop once we exceed the limit.
        need = max_bytes + 1 - total
        if need <= 0:
            raise MediaStoreError("file too large")
        chunk = await upload.read(min(64 * 1024, need))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise MediaStoreError("file too large")
        chunks.append(chunk)
    return b"".join(chunks)


def _ext_of(filename: str) -> str:
    name = Path(filename).name
    if ".." in name or "/" in name or "\\" in name:
        raise MediaStoreError("invalid filename")
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise MediaStoreError("unsupported file type")
    return ext


def _validate_svg(data: bytes, content_type: str | None) -> None:
    ct = (content_type or "").split(";")[0].strip().lower()
    if not ct or ct not in _SVG_OK_TYPES:
        raise MediaStoreError("invalid content type")
    text = data.decode("utf-8", errors="ignore")
    lower = text.lower()
    if "<svg" not in lower:
        raise MediaStoreError("invalid svg content")
    if "<script" in lower:
        raise MediaStoreError("svg must not contain script")
    if "<foreignobject" in lower:
        raise MediaStoreError("svg must not contain foreignObject")
    if _SVG_JS_URL_RE.search(text):
        raise MediaStoreError("svg must not contain javascript urls")
    if _SVG_EVENT_RE.search(text):
        raise MediaStoreError("svg must not contain event handlers")


def _validate_payload(ext: str, data: bytes, content_type: str | None = None) -> None:
    if len(data) > MAX_BYTES:
        raise MediaStoreError("file too large")
    magic = ALLOWED[ext]
    if magic is not None:
        if not data.startswith(magic):
            raise MediaStoreError("invalid file content")
        return
    _validate_svg(data, content_type)


def save_branding_file(
    org_id: int,
    kind: str,
    filename: str,
    data: bytes,
    data_dir: Path,
    *,
    content_type: str | None = None,
) -> str:
    """Persist upload under data_dir/{org_id}/{kind}{ext}; return relative path."""
    if kind not in _KINDS:
        raise MediaStoreError("invalid kind")
    if ".." in filename:
        raise MediaStoreError("invalid filename")
    ext = _ext_of(filename)
    _validate_payload(ext, data, content_type=content_type)

    org_dir = (data_dir / str(org_id)).resolve()
    data_root = data_dir.resolve()
    if not org_dir.is_relative_to(data_root):
        raise MediaStoreError("path escape")
    org_dir.mkdir(parents=True, exist_ok=True)

    out_name = f"{kind}{ext}"
    dest = (org_dir / out_name).resolve()
    if not dest.is_relative_to(org_dir):
        raise MediaStoreError("path escape")
    dest.write_bytes(data)
    return f"{org_id}/{out_name}"


def branding_file_abs(data_dir: Path, org_id: int, name: str) -> Path:
    """Resolve media filename under data_dir/{org_id}; raise on traversal."""
    if not name or ".." in name or "/" in name or "\\" in name:
        raise MediaStoreError("invalid filename")
    org_dir = (data_dir / str(org_id)).resolve()
    data_root = data_dir.resolve()
    if not org_dir.is_relative_to(data_root):
        raise MediaStoreError("path escape")
    path = (org_dir / Path(name).name).resolve()
    if not path.is_relative_to(org_dir):
        raise MediaStoreError("path escape")
    return path


def delete_branding_file(data_dir: Path, relative_path: str | None) -> None:
    """Delete a previously saved relative branding path if it stays under data_dir."""
    if not relative_path:
        return
    if ".." in relative_path:
        return
    parts = Path(relative_path).parts
    if len(parts) != 2:
        return
    org_part, name = parts
    if not org_part.isdigit():
        return
    try:
        path = branding_file_abs(data_dir, int(org_part), name)
    except MediaStoreError:
        return
    if path.is_file():
        path.unlink()
