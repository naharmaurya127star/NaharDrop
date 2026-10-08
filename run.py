#!/usr/bin/env python
"""NaharDrop entry point: parses CLI flags, wires up app.config.settings,
detects the LAN IP, and starts the single-process uvicorn server.

Run as a single process by design: upload progress, pending-device approval,
and session state all live in memory (see app/security.py and app/uploads.py)
and are not shared across workers, so --workers > 1 would break resume and
device approval.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn

# Windows terminals often default stdout to a legacy codepage (cp1252) that
# can't encode the QR code's block characters. UTF-8 is safe on modern
# Windows Terminal / PowerShell / macOS / Linux terminals alike.
# Also force line buffering: when stdout isn't a real terminal (piped,
# redirected to a file, run in the background), Python block-buffers it, so
# the startup banner (QR/PIN) can sit invisible in the buffer for a long
# time behind uvicorn's own immediately-flushed log lines.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

from app.config import settings
from app.network import get_lan_ip
from app.security import generate_pin, generate_token


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NaharDrop - LAN file transfer between your phone and laptop")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default 8000)")
    parser.add_argument("--dest", default="./received", help="Folder to save files uploaded from your phone")
    parser.add_argument("--https", action="store_true", help="Serve over HTTPS (self-signed unless --cert-file is given)")
    parser.add_argument("--cert-file", default=None, help="Use this certificate instead of an auto-generated one (e.g. from mkcert)")
    parser.add_argument("--key-file", default=None, help="Private key matching --cert-file")
    parser.add_argument("--no-pin", action="store_true", help="Disable the one-time PIN / device approval gate")
    parser.add_argument(
        "--advertise-ip",
        default=os.environ.get("NAHARDROP_ADVERTISE_IP") or None,
        help="IP to show in the QR/URL instead of auto-detecting (needed in Docker without --network host; "
        "can also be set via the NAHARDROP_ADVERTISE_IP env var)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    settings.host = args.host
    settings.port = args.port
    settings.dest_dir = Path(args.dest).resolve()
    settings.https = args.https
    settings.require_pin = not args.no_pin
    settings.pin = generate_pin() if settings.require_pin else ""
    settings.qr_token = generate_token() if settings.require_pin else ""
    settings.lan_ip = args.advertise_ip or get_lan_ip()
    settings.ensure_dirs()

    ssl_kwargs = {}
    if settings.https:
        if args.cert_file and args.key_file:
            cert_file, key_file = Path(args.cert_file), Path(args.key_file)
        else:
            from app.tls import ensure_self_signed_cert

            cert_file, key_file = ensure_self_signed_cert(settings.data_dir, settings.lan_ip)
        settings.cert_file, settings.key_file = cert_file, key_file
        ssl_kwargs = {"ssl_certfile": str(cert_file), "ssl_keyfile": str(key_file)}

    from app.main import create_app, print_startup_banner

    app = create_app()
    print_startup_banner()

    uvicorn.run(app, host=settings.host, port=settings.port, **ssl_kwargs)


if __name__ == "__main__":
    main()
