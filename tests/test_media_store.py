"""Unit tests for branding media_store hardening."""

from pathlib import Path

import pytest

from apps.api.media_store import (
    MAX_BYTES,
    MediaStoreError,
    read_upload_capped,
    save_branding_file,
)


class _FakeUpload:
    def __init__(self, data: bytes, content_length: str | None = None):
        self._data = data
        self._pos = 0
        self.size = int(content_length) if content_length is not None else None
        self.headers = {}
        if content_length is not None:
            self.headers["content-length"] = content_length

    async def read(self, n: int = -1) -> bytes:
        if n < 0:
            n = len(self._data) - self._pos
        chunk = self._data[self._pos : self._pos + n]
        self._pos += len(chunk)
        return chunk


@pytest.mark.asyncio
async def test_read_upload_capped_rejects_oversized_stream():
    data = b"x" * (MAX_BYTES + 1)
    with pytest.raises(MediaStoreError, match="too large"):
        await read_upload_capped(_FakeUpload(data))


@pytest.mark.asyncio
async def test_read_upload_capped_rejects_content_length():
    with pytest.raises(MediaStoreError, match="too large"):
        await read_upload_capped(_FakeUpload(b"x", content_length=str(MAX_BYTES + 5)))


def test_save_rejects_dangerous_svg(tmp_path: Path):
    dirty = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>'
    with pytest.raises(MediaStoreError):
        save_branding_file(
            1,
            "logo",
            "x.svg",
            dirty,
            tmp_path,
            content_type="image/svg+xml",
        )


def test_save_rejects_svg_missing_content_type(tmp_path: Path):
    safe = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="1"/></svg>'
    with pytest.raises(MediaStoreError, match="content type"):
        save_branding_file(1, "logo", "x.svg", safe, tmp_path, content_type=None)
