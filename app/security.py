"""Filename sanitization, path-traversal protection, PIN/session/device auth.

The sanitization helpers are used from Phase 2 onward (any code that writes a
client-supplied name to disk must go through them); the PIN/session/device
approval pieces are added in Phase 4.
"""
from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.config import MAX_FILENAME_LENGTH

_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str) -> str:
    """Strip path components and unsafe characters from a client-supplied name.

    Guards against path traversal (`../../etc/passwd`), null-byte injection,
    reserved Windows device names (`CON`, `NUL`, ...), and empty/overlong
    names. Always returns a non-empty, single-segment filename.
    """
    name = name.strip()
    # Drop any directory components the client tried to sneak in (both
    # separators, since a Windows client may send backslashes to a server
    # running on POSIX or vice versa).
    name = name.replace("\\", "/").split("/")[-1]
    name = _UNSAFE_CHARS.sub("_", name)
    name = name.strip(" .")

    if not name:
        name = "file"

    stem = name.rsplit(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED:
        name = f"_{name}"

    if len(name) > MAX_FILENAME_LENGTH:
        suffix = ""
        if "." in name:
            base, ext = name.rsplit(".", 1)
            if len(ext) <= 15:
                suffix = "." + ext
                base = base[: MAX_FILENAME_LENGTH - len(suffix)]
                name = base + suffix
        if not suffix:
            name = name[:MAX_FILENAME_LENGTH]

    return name


def sanitize_relpath(rel_path: str) -> str:
    """Sanitize a client-supplied relative path (folder drop/upload).

    Drops `.`/`..`/empty segments outright (rather than trying to resolve
    them), then runs each remaining segment through `sanitize_filename`.
    Always returns at least one segment.
    """
    rel_path = rel_path.replace("\\", "/")
    segments = [s for s in rel_path.split("/") if s not in ("", ".", "..")]
    segments = [sanitize_filename(s) for s in segments] or ["file"]
    return "/".join(segments)


def unique_destination(directory: Path, filename: str) -> Path:
    """Return a path in `directory` for `filename`, appending ` (n)` on collision."""
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem, _, ext = filename.rpartition(".")
    if not stem:
        stem, ext = filename, ""
    n = 1
    while True:
        new_name = f"{stem} ({n})" + (f".{ext}" if ext else "")
        candidate = directory / new_name
        if not candidate.exists():
            return candidate
        n += 1


def safe_join(base: Path, *parts: str) -> Path:
    """Join `parts` onto `base` and guarantee the result stays inside `base`.

    Raises `ValueError` if the resolved path would escape `base` (path
    traversal attempt), e.g. via `..` segments or absolute-path injection.
    """
    base = base.resolve()
    candidate = base
    for part in parts:
        candidate = candidate / part
    resolved = candidate.resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ValueError(f"path traversal attempt: {parts!r}") from None
    return resolved


# --------------------------------------------------------------------------
# Phase 4: one-time PIN, session tokens, device approval
# --------------------------------------------------------------------------

def generate_pin() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_token() -> str:
    return secrets.token_urlsafe(24)


@dataclass
class PendingDevice:
    token: str
    device_name: str
    requested_at: float = field(default_factory=time.time)


@dataclass
class Session:
    token: str
    device_name: str
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_seen = time.time()

    def is_expired(self, timeout_seconds: float) -> bool:
        return (time.time() - self.last_seen) > timeout_seconds


class SessionStore:
    """In-memory store for pending-approval devices and approved sessions.

    Single-process, in-memory by design: NaharDrop runs as one laptop-local
    server for one user, so there is no need for persistence or cross-process
    sharing of live session state (approved sessions are also recorded to
    SQLite for history, separately, in app/history.py).
    """

    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        self._pending: dict[str, PendingDevice] = {}
        self._sessions: dict[str, Session] = {}

    def add_pending(self, device_name: str) -> PendingDevice:
        token = generate_token()
        pending = PendingDevice(token=token, device_name=device_name)
        self._pending[token] = pending
        return pending

    def pop_pending(self, token: str) -> PendingDevice | None:
        return self._pending.pop(token, None)

    def list_pending(self) -> list[PendingDevice]:
        cutoff = time.time() - 300
        self._pending = {t: p for t, p in self._pending.items() if p.requested_at >= cutoff}
        return list(self._pending.values())

    def approve(self, token: str) -> Session | None:
        pending = self.pop_pending(token)
        if pending is None:
            return None
        session = Session(token=token, device_name=pending.device_name)
        self._sessions[token] = session
        return session

    def deny(self, token: str) -> bool:
        return self.pop_pending(token) is not None

    def get(self, token: str) -> Session | None:
        session = self._sessions.get(token)
        if session is None:
            return None
        if session.is_expired(self.timeout_seconds):
            del self._sessions[token]
            return None
        session.touch()
        return session

    def revoke(self, token: str) -> bool:
        return self._sessions.pop(token, None) is not None

    def list_sessions(self) -> list[Session]:
        self._sessions = {
            t: s for t, s in self._sessions.items() if not s.is_expired(self.timeout_seconds)
        }
        return list(self._sessions.values())
