"""Phase 2: chunked upload engine.

Chunks are written directly to a pre-sized `.part` file at their byte offset
(no whole-file buffering), so upload order doesn't matter and a dropped
connection can resume by asking which chunk indices are still missing. A
`.json` manifest sits next to the `.part` file recording which chunks have
landed, so resume survives a server restart too, not just a network blip.
"""
from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

import aiofiles

from app.security import safe_join, sanitize_filename, sanitize_relpath, unique_destination


@dataclass
class UploadState:
    upload_id: str
    filename: str
    size: int
    chunk_size: int
    total_chunks: int
    part_path: Path
    manifest_path: Path
    rel_dir: str = ""  # sanitized folder path this file lands under, e.g. "myfolder/sub"
    device: str = ""
    received: set[int] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    created_at: float = field(default_factory=time.time)

    def is_complete(self) -> bool:
        return len(self.received) == self.total_chunks


class UploadManager:
    def __init__(self, tmp_dir: Path, dest_dir: Path) -> None:
        self.tmp_dir = tmp_dir
        self.dest_dir = dest_dir
        self._uploads: dict[str, UploadState] = {}

    def _manifest_dict(self, state: UploadState) -> dict:
        return {
            "filename": state.filename,
            "size": state.size,
            "chunk_size": state.chunk_size,
            "total_chunks": state.total_chunks,
            "received": sorted(state.received),
        }

    async def _save_manifest(self, state: UploadState) -> None:
        data = json.dumps(self._manifest_dict(state))
        async with aiofiles.open(state.manifest_path, "w", encoding="utf-8") as f:
            await f.write(data)

    async def create_upload(
        self, filename: str, size: int, chunk_size: int, device: str = "", rel_dir: str = ""
    ) -> UploadState:
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        safe_name = sanitize_filename(filename)
        safe_rel_dir = sanitize_relpath(rel_dir) if rel_dir else ""
        upload_id = uuid.uuid4().hex
        size = max(0, size)
        total_chunks = max(1, math.ceil(size / chunk_size)) if size > 0 else 1
        part_path = self.tmp_dir / f"{upload_id}.part"
        manifest_path = self.tmp_dir / f"{upload_id}.json"

        # Pre-size the file so chunks can land at any offset in any order.
        async with aiofiles.open(part_path, "wb") as f:
            if size > 0:
                await f.seek(size - 1)
                await f.write(b"\0")

        state = UploadState(
            upload_id=upload_id,
            filename=safe_name,
            size=size,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            part_path=part_path,
            manifest_path=manifest_path,
            rel_dir=safe_rel_dir,
            device=device,
        )
        self._uploads[upload_id] = state
        await self._save_manifest(state)
        return state

    def get(self, upload_id: str) -> UploadState | None:
        return self._uploads.get(upload_id)

    async def write_chunk(self, state: UploadState, index: int, stream: AsyncIterator[bytes]) -> None:
        if index < 0 or index >= state.total_chunks:
            raise ValueError("chunk index out of range")
        offset = index * state.chunk_size
        written = 0
        async with aiofiles.open(state.part_path, "r+b") as f:
            await f.seek(offset)
            async for piece in stream:
                if piece:
                    await f.write(piece)
                    written += len(piece)
        async with state.lock:
            state.received.add(index)
            await self._save_manifest(state)

    def status(self, state: UploadState) -> dict:
        missing = [i for i in range(state.total_chunks) if i not in state.received]
        return {
            "upload_id": state.upload_id,
            "filename": state.filename,
            "size": state.size,
            "total_chunks": state.total_chunks,
            "received": sorted(state.received),
            "missing": missing,
            "complete": state.is_complete(),
        }

    async def finalize(self, state: UploadState) -> Path:
        if not state.is_complete():
            raise ValueError("upload is not complete yet")
        target_dir = (
            safe_join(self.dest_dir, *state.rel_dir.split("/")) if state.rel_dir else self.dest_dir
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        final_path = unique_destination(target_dir, state.filename)
        state.part_path.replace(final_path)
        state.manifest_path.unlink(missing_ok=True)
        self._uploads.pop(state.upload_id, None)
        return final_path

    async def cancel(self, upload_id: str) -> bool:
        state = self._uploads.pop(upload_id, None)
        if state is None:
            return False
        state.part_path.unlink(missing_ok=True)
        state.manifest_path.unlink(missing_ok=True)
        return True
