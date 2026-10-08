"""Push notifications for the phone's Receive tab (and dashboard lists that
care about outbox changes), so clients don't need to poll every couple of
seconds. Kept outside app/routes/download.py's router (which gates every
HTTP route behind require_session via a Request-typed dependency) since a
WebSocket connection needs its own auth check against the ASGI scope."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings

router = APIRouter()


@router.websocket("/ws/outbox")
async def outbox_ws(websocket: WebSocket):
    if settings.require_pin:
        token = websocket.cookies.get("nd_session")
        store = websocket.app.state.session_store
        if not token or store.get(token) is None:
            await websocket.close(code=4401)
            return

    ws_manager = websocket.app.state.ws_manager
    await ws_manager.connect_outbox(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect_outbox(websocket)
