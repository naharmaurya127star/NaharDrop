"""Central runtime configuration for NaharDrop.

A single `Settings` instance is created at process startup (see run.py) and
stored in `settings`. Routes import `settings` directly rather than re-parsing
args, since uvicorn's reload workers and the test suite both need a plain
importable object.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

# BASE_DIR anchors user-writable defaults (received/, data/): next to the
# project root normally, or next to the .exe/binary itself when frozen -
# never PyInstaller's temp extraction dir, which is wiped after each run.
#
# RESOURCE_DIR anchors read-only app resources (templates/, static/): the
# project root normally, or PyInstaller's extracted bundle when frozen.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(sys._MEIPASS)  # type: ignore[attr-defined]
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    RESOURCE_DIR = BASE_DIR

CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB, matches the spec'd upload chunk size
SESSION_TIMEOUT_SECONDS = 24 * 60 * 60  # 24h sliding session lifetime
PENDING_APPROVAL_TIMEOUT_SECONDS = 120
MAX_FILENAME_LENGTH = 180


@dataclass
class Settings:
    host: str = "0.0.0.0"
    port: int = 8000
    dest_dir: Path = field(default_factory=lambda: BASE_DIR / "received")
    data_dir: Path = field(default_factory=lambda: BASE_DIR / "data")
    upload_tmp_dir: Path = field(default_factory=lambda: BASE_DIR / "tmp_uploads")
    https: bool = False
    cert_file: Path | None = None
    key_file: Path | None = None
    require_pin: bool = True
    pin: str = ""
    qr_token: str = ""
    lan_ip: str = "127.0.0.1"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "nahardrop.db"

    def ensure_dirs(self) -> None:
        self.dest_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_tmp_dir.mkdir(parents=True, exist_ok=True)

    def base_url(self, scheme: str | None = None) -> str:
        scheme = scheme or ("https" if self.https else "http")
        return f"{scheme}://{self.lan_ip}:{self.port}"


settings = Settings()
