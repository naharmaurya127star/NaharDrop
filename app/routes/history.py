"""Phase 5: transfer history API (laptop-side, for the dashboard)."""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
async def get_history(request: Request, limit: int = 100):
    return await request.app.state.history.list(limit=limit)
