"""Phase 5: laptop-trusted management of the received folder.

Not behind the phone pairing gate - these actions are only ever triggered
from the dashboard page itself, which runs on the laptop. The "relay" route
is what makes Android -> iPhone (or any phone -> phone) transfer work
through the web interface alone: a file one phone uploaded into ./received
can be copied into the outbox for a different phone to then download,
without the laptop operator needing to touch the filesystem.
"""
from __future__ import annotations

import asyncio
import shutil

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.security import sanitize_filename, unique_destination

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("/received")
async def list_received():
    if not settings.dest_dir.exists():
        return []
    items = [
        {"filename": p.name, "size": p.stat().st_size}
        for p in sorted(settings.dest_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if p.is_file()
    ]
    return items


@router.post("/relay")
async def relay_to_outbox(filename: str, request: Request):
    safe_name = sanitize_filename(filename)
    src = settings.dest_dir / safe_name
    if not src.is_file():
        raise HTTPException(404, "file not found in the received folder")

    outbox = request.app.state.outbox
    outbox_dir = request.app.state.send_manager.dest_dir
    outbox_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_destination(outbox_dir, safe_name)
    await asyncio.to_thread(shutil.copy2, src, dest)

    item = outbox.add(name=dest.name, rel_path=dest.name, size=dest.stat().st_size, path=dest, group=None)
    await request.app.state.history.record(direction="send", filename=item.name, size=item.size, device="laptop")
    await request.app.state.ws_manager.broadcast_outbox({"type": "outbox_changed"})
    return {"item_id": item.item_id, "filename": item.name}
