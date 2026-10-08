"""Phase 4: PIN/QR-token pairing, device approval, and session management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.config import SESSION_TIMEOUT_SECONDS, settings
from app.security import Session, SessionStore

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_session_store(request: Request) -> SessionStore:
    return request.app.state.session_store


@router.get("/config")
async def auth_config():
    return {"require_pin": settings.require_pin}


class PairRequest(BaseModel):
    device_name: str = "Unknown device"
    token: str | None = None  # from the QR code's ?t= param
    pin: str | None = None  # typed in manually


@router.post("/pair")
async def pair(payload: PairRequest, request: Request):
    if not settings.require_pin:
        raise HTTPException(400, "pairing is disabled on this server")

    valid = (payload.token and payload.token == settings.qr_token) or (
        payload.pin and payload.pin == settings.pin
    )
    if not valid:
        raise HTTPException(401, "invalid PIN or link - ask for a fresh one on the laptop")

    store = get_session_store(request)
    pending = store.add_pending(payload.device_name or "Unknown device")

    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is not None:
        await ws_manager.broadcast_dashboard(
            {"type": "pending_device", "token": pending.token, "device_name": pending.device_name}
        )

    return {"pending_token": pending.token}


@router.get("/pair-status/{token}")
async def pair_status(token: str, request: Request, response: Response):
    store = get_session_store(request)
    session = store.get(token)
    if session:
        response.set_cookie(
            "nd_session",
            token,
            max_age=SESSION_TIMEOUT_SECONDS,
            httponly=True,
            samesite="lax",
        )
        return {"status": "approved", "device_name": session.device_name}
    if any(p.token == token for p in store.list_pending()):
        return {"status": "pending"}
    return {"status": "denied"}


@router.get("/pending")
async def list_pending(request: Request):
    store = get_session_store(request)
    return [
        {"token": p.token, "device_name": p.device_name, "requested_at": p.requested_at}
        for p in store.list_pending()
    ]


@router.post("/approve/{token}")
async def approve(token: str, request: Request):
    store = get_session_store(request)
    session = store.approve(token)
    if session is None:
        raise HTTPException(404, "pairing request not found or expired")
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is not None:
        await ws_manager.broadcast_dashboard({"type": "device_approved", "device_name": session.device_name})
    return {"approved": True, "device_name": session.device_name}


@router.post("/deny/{token}")
async def deny(token: str, request: Request):
    store = get_session_store(request)
    if not store.deny(token):
        raise HTTPException(404, "pairing request not found or expired")
    return {"denied": True}


@router.get("/sessions")
async def list_sessions(request: Request):
    store = get_session_store(request)
    return [
        {"device_name": s.device_name, "created_at": s.created_at, "last_seen": s.last_seen}
        for s in store.list_sessions()
    ]


@router.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    ws_manager = websocket.app.state.ws_manager
    await ws_manager.connect_dashboard(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect_dashboard(websocket)


def require_session(request: Request) -> Session | None:
    """FastAPI dependency gating phone-facing routes once pairing is enabled.

    Returns None (no-op) when the server was started with --no-pin, so the
    same routes work unauthenticated in that mode.
    """
    if not settings.require_pin:
        return None
    token = request.cookies.get("nd_session")
    store = get_session_store(request)
    session = store.get(token) if token else None
    if session is None:
        raise HTTPException(401, "not authorized - pair this device from the laptop first")
    return session


SessionDep = Depends(require_session)
