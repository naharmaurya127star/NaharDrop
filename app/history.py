"""Phase 5: transfer history, persisted to SQLite.

Records when a transfer completes on the server side: a phone finishing an
upload, or the laptop finishing a send into the outbox. Streaming downloads
don't get a "the phone definitely received this" event (StreamingResponse
has no completion hook worth relying on), so "sent" is recorded at the point
the file became available, not confirmed-delivered - documented in README.
"""
from __future__ import annotations

import asyncio
import sqlite3
import time
from pathlib import Path


class HistoryStore:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                direction TEXT NOT NULL,
                filename TEXT NOT NULL,
                size INTEGER NOT NULL,
                device TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
            """
        )
        self._conn.commit()

    def _record_sync(self, direction: str, filename: str, size: int, device: str) -> None:
        self._conn.execute(
            "INSERT INTO transfers (direction, filename, size, device, timestamp) VALUES (?, ?, ?, ?, ?)",
            (direction, filename, size, device, time.time()),
        )
        self._conn.commit()

    async def record(self, direction: str, filename: str, size: int, device: str = "") -> None:
        await asyncio.to_thread(self._record_sync, direction, filename, size, device)

    def _list_sync(self, limit: int) -> list[dict]:
        rows = self._conn.execute(
            "SELECT direction, filename, size, device, timestamp FROM transfers ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"direction": r[0], "filename": r[1], "size": r[2], "device": r[3], "timestamp": r[4]}
            for r in rows
        ]

    async def list(self, limit: int = 100) -> list[dict]:
        return await asyncio.to_thread(self._list_sync, limit)

    def close(self) -> None:
        self._conn.close()
