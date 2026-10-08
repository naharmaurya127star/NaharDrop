"""Byte-range-aware file streaming, shared by single-file and preview downloads."""
from __future__ import annotations

import re
from pathlib import Path
from typing import AsyncIterator

import aiofiles
from fastapi import Request
from fastapi.responses import StreamingResponse

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")
_READ_SIZE = 1024 * 1024


async def _read_range(path: Path, start: int, end: int) -> AsyncIterator[bytes]:
    remaining = end - start + 1
    async with aiofiles.open(path, "rb") as f:
        await f.seek(start)
        while remaining > 0:
            piece = await f.read(min(_READ_SIZE, remaining))
            if not piece:
                break
            remaining -= len(piece)
            yield piece


def stream_file_response(
    request: Request,
    path: Path,
    download_name: str,
    content_type: str = "application/octet-stream",
    disposition: str = "attachment",
) -> StreamingResponse:
    """Stream `path`, honouring a `Range` header for resumable/seekable downloads."""
    size = path.stat().st_size
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'{disposition}; filename="{download_name}"',
    }

    range_header = request.headers.get("range")
    if range_header:
        match = _RANGE_RE.match(range_header)
        if match:
            start_s, end_s = match.groups()
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else size - 1
            end = min(end, size - 1) if size > 0 else -1
            if size == 0 or start > end or start >= size:
                headers["Content-Range"] = f"bytes */{size}"
                return StreamingResponse(iter(()), status_code=416, headers=headers)
            headers["Content-Range"] = f"bytes {start}-{end}/{size}"
            headers["Content-Length"] = str(end - start + 1)
            return StreamingResponse(
                _read_range(path, start, end),
                status_code=206,
                media_type=content_type,
                headers=headers,
            )

    headers["Content-Length"] = str(size)
    return StreamingResponse(
        _read_range(path, 0, max(size - 1, 0)) if size > 0 else iter(()),
        status_code=200,
        media_type=content_type,
        headers=headers,
    )
