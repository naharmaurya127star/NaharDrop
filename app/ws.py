"""Phase 4: WebSocket push to the laptop dashboard (pending-device alerts,
connected-device-list and outbox changes), so approval prompts and lists
update instantly instead of only on the next poll."""
from __future__ import annotations

from fastapi import WebSocket


class WSManager:
    def __init__(self) -> None:
        self.dashboard_sockets: set[WebSocket] = set()
        self.outbox_sockets: set[WebSocket] = set()

    async def connect_dashboard(self, ws: WebSocket) -> None:
        await ws.accept()
        self.dashboard_sockets.add(ws)

    def disconnect_dashboard(self, ws: WebSocket) -> None:
        self.dashboard_sockets.discard(ws)

    async def broadcast_dashboard(self, message: dict) -> None:
        await self._broadcast(self.dashboard_sockets, message)

    async def connect_outbox(self, ws: WebSocket) -> None:
        await ws.accept()
        self.outbox_sockets.add(ws)

    def disconnect_outbox(self, ws: WebSocket) -> None:
        self.outbox_sockets.discard(ws)

    async def broadcast_outbox(self, message: dict) -> None:
        await self._broadcast(self.outbox_sockets, message)

    @staticmethod
    async def _broadcast(sockets: set[WebSocket], message: dict) -> None:
        dead = []
        for ws in sockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            sockets.discard(ws)
