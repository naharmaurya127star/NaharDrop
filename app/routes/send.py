"""Phase 3: laptop -> outbox ingestion (dashboard drag-and-drop)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import CHUNK_SIZE
from app.outbox import OutboxManager
from app.uploads import UploadManager

router = APIRouter(prefix="/api/send", tags=["send"])


def get_send_manager(request: Request) -> UploadManager:
    return request.app.state.send_manager


def get_outbox(request: Request) -> OutboxManager:
    return request.app.state.outbox


class InitRequest(BaseModel):
    filename: str
    size: int = Field(ge=0)
    chunk_size: int | None = None
    rel_dir: str | None = None  # folder path when dropping a whole folder
    group: str | None = None  # top-level folder name, shared by all files in that folder


@router.post("/init")
async def init_send(payload: InitRequest, request: Request):
    manager = get_send_manager(request)
    chunk_size = payload.chunk_size if payload.chunk_size and payload.chunk_size > 0 else CHUNK_SIZE
    state = await manager.create_upload(
        filename=payload.filename,
        size=payload.size,
        chunk_size=chunk_size,
        rel_dir=payload.rel_dir or "",
    )
    return {
        "upload_id": state.upload_id,
        "filename": state.filename,
        "chunk_size": state.chunk_size,
        "total_chunks": state.total_chunks,
    }


@router.put("/{upload_id}/chunk/{index}")
async def send_chunk(upload_id: str, index: int, request: Request):
    manager = get_send_manager(request)
    state = manager.get(upload_id)
    if state is None:
        raise HTTPException(404, "unknown upload_id")
    try:
        await manager.write_chunk(state, index, request.stream())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return manager.status(state)


@router.get("/{upload_id}/status")
async def send_status(upload_id: str, request: Request):
    manager = get_send_manager(request)
    state = manager.get(upload_id)
    if state is None:
        raise HTTPException(404, "unknown upload_id")
    return manager.status(state)


@router.post("/{upload_id}/complete")
async def complete_send(upload_id: str, request: Request, group: str | None = None):
    manager = get_send_manager(request)
    outbox = get_outbox(request)
    state = manager.get(upload_id)
    if state is None:
        raise HTTPException(404, "unknown upload_id")
    try:
        final_path = await manager.finalize(state)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    rel_path = f"{state.rel_dir}/{final_path.name}" if state.rel_dir else final_path.name
    item = outbox.add(
        name=final_path.name,
        rel_path=rel_path,
        size=state.size,
        path=final_path,
        group=group,
    )
    await request.app.state.history.record(
        direction="send", filename=item.name, size=state.size, device="laptop"
    )
    await request.app.state.ws_manager.broadcast_outbox({"type": "outbox_changed"})
    return {"item_id": item.item_id, "filename": item.name}


@router.delete("/{upload_id}")
async def cancel_send(upload_id: str, request: Request):
    manager = get_send_manager(request)
    ok = await manager.cancel(upload_id)
    if not ok:
        raise HTTPException(404, "unknown upload_id")
    return {"cancelled": True}
