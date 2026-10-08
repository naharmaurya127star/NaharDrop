"""Phase 3: phone-side listing/downloading of files the laptop sent."""
from __future__ import annotations

import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from zipstream import ZipStream

from app.outbox import OutboxManager
from app.routes.auth import require_session
from app.streaming import stream_file_response

router = APIRouter(prefix="/api/outbox", tags=["outbox"], dependencies=[Depends(require_session)])


def get_outbox(request: Request) -> OutboxManager:
    return request.app.state.outbox


@router.get("")
async def list_outbox(request: Request):
    return get_outbox(request).listing()


@router.get("/file/{item_id}")
async def download_file(item_id: str, request: Request):
    outbox = get_outbox(request)
    item = outbox.get(item_id)
    if item is None or not item.path.exists():
        raise HTTPException(404, "file not found")
    content_type, _ = mimetypes.guess_type(item.name)
    return stream_file_response(request, item.path, item.name, content_type or "application/octet-stream")


@router.get("/file/{item_id}/preview")
async def preview_file(item_id: str, request: Request):
    """Same bytes as /file but with an inline Content-Disposition, for
    <img>/<video> tags to render in-page instead of triggering a download."""
    outbox = get_outbox(request)
    item = outbox.get(item_id)
    if item is None or not item.path.exists():
        raise HTTPException(404, "file not found")
    content_type, _ = mimetypes.guess_type(item.name)
    return stream_file_response(
        request, item.path, item.name, content_type or "application/octet-stream", disposition="inline"
    )


@router.get("/folder/{group}/zip")
async def download_folder_zip(group: str, request: Request):
    outbox = get_outbox(request)
    items = outbox.items_in_group(group)
    if not items:
        raise HTTPException(404, "folder not found")

    zs = ZipStream(sized=False)
    for item in items:
        if item.path.exists():
            zs.add_path(str(item.path), arcname=item.rel_path)

    headers = {"Content-Disposition": f'attachment; filename="{group}.zip"'}
    return StreamingResponse(zs, media_type="application/zip", headers=headers)


@router.delete("/{item_id}")
async def remove_item(item_id: str, request: Request):
    outbox = get_outbox(request)
    if not outbox.remove(item_id):
        raise HTTPException(404, "file not found")
    await request.app.state.ws_manager.broadcast_outbox({"type": "outbox_changed"})
    return {"removed": True}
