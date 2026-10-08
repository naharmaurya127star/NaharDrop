"""FastAPI application factory and terminal startup banner."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import RESOURCE_DIR, SESSION_TIMEOUT_SECONDS, settings
from app.history import HistoryStore
from app.outbox import OutboxManager
from app.routes import auth, download, history, library, pages, realtime, send, upload
from app.security import SessionStore
from app.uploads import UploadManager
from app.ws import WSManager


def create_app() -> FastAPI:
    app = FastAPI(title="NaharDrop")
    app.state.upload_manager = UploadManager(settings.upload_tmp_dir, settings.dest_dir)

    outbox_dir = settings.data_dir / "outbox"
    app.state.send_manager = UploadManager(settings.upload_tmp_dir, outbox_dir)
    app.state.outbox = OutboxManager(outbox_dir)

    app.state.session_store = SessionStore(SESSION_TIMEOUT_SECONDS)
    app.state.ws_manager = WSManager()
    app.state.history = HistoryStore(settings.db_path)

    app.mount("/static", StaticFiles(directory=str(RESOURCE_DIR / "app" / "static")), name="static")
    app.include_router(pages.router)
    app.include_router(auth.router)
    app.include_router(upload.router)
    app.include_router(send.router)
    app.include_router(download.router)
    app.include_router(history.router)
    app.include_router(library.router)
    app.include_router(realtime.router)
    return app


def print_startup_banner() -> None:
    from app.network import make_qr_ascii

    url = settings.base_url()
    mobile_url = f"{url}/m"
    qr_target = f"{mobile_url}?t={settings.qr_token}" if settings.require_pin else mobile_url
    print("=" * 60)
    print(" NaharDrop is running")
    print("=" * 60)
    print(f" Dashboard (this laptop): {url}")
    print(f" Phone URL:               {mobile_url}")
    if settings.require_pin:
        print(f" PIN:                     {settings.pin}")
    print(f" Saving uploads to:       {settings.dest_dir}")
    print()
    print(make_qr_ascii(qr_target))
    print("Scan the QR code above with your phone's camera, or type the Phone")
    print("URL into its browser. Press Ctrl+C to stop the server.")
    print("=" * 60)
