"""Phase 2: chunked upload API (phone -> laptop)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import CHUNK_SIZE
from app.routes.auth import require_session
from app.uploads import UploadManager

router = APIRouter(prefix="/api/upload", tags=["upload"], dependencies=[Depends(require_session)])


def get_upload_manager(request: Request) -> UploadManager:
    return request.app.state.upload_manager


class InitRequest(BaseModel):
    filename: str
    size: int = Field(ge=0)
    chunk_size: int | None = None
    device: str | None = None


@router.post("/init")
async def init_upload(payload: InitRequest, request: Request):
    manager = get_upload_manager(request)
    chunk_size = payload.chunk_size if payload.chunk_size and payload.chunk_size > 0 else CHUNK_SIZE
    state = await manager.create_upload(
        filename=payload.filename,
        size=payload.size,
        chunk_size=chunk_size,
        device=payload.device or "unknown device",
    )
    return {
        "upload_id": state.upload_id,
        "filename": state.filename,
        "chunk_size": state.chunk_size,
        "total_chunks": state.total_chunks,
    }


@router.put("/{upload_id}/chunk/{index}")
async def upload_chunk(upload_id: str, index: int, request: Request):
    manager = get_upload_manager(request)
    state = manager.get(upload_id)
    if state is None:
        raise HTTPException(404, "unknown upload_id (it may have expired or already completed)")
    try:
        await manager.write_chunk(state, index, request.stream())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return manager.status(state)


@router.get("/{upload_id}/status")
async def upload_status(upload_id: str, request: Request):
    manager = get_upload_manager(request)
    state = manager.get(upload_id)
    if state is None:
        raise HTTPException(404, "unknown upload_id")
    return manager.status(state)


@router.post("/{upload_id}/complete")
async def complete_upload(upload_id: str, request: Request):
    manager = get_upload_manager(request)
    state = manager.get(upload_id)
    if state is None:
        raise HTTPException(404, "unknown upload_id")
    try:
        final_path = await manager.finalize(state)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    await request.app.state.history.record(
        direction="upload", filename=final_path.name, size=state.size, device=state.device
    )

    return {"filename": final_path.name}


@router.delete("/{upload_id}")
async def cancel_upload(upload_id: str, request: Request):
    manager = get_upload_manager(request)
    ok = await manager.cancel(upload_id)
    if not ok:
        raise HTTPException(404, "unknown upload_id")
    return {"cancelled": True}
