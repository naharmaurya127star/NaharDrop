# NaharDrop

Build the complete NaharDrop project end to end, working through the phases below one by one. After each phase, run and test it (write pytest tests where useful), fix any bugs, and only then move on. Make sensible decisions and note them in README.md.

**Stack:** Python 3.11+, FastAPI + Uvicorn, WebSocket, plain HTML/CSS/JS frontend (no heavy frameworks), qrcode library. Cross-platform (Windows + macOS first).

## Phase 1 - Server
Run on 0.0.0.0:8000, auto-detect the laptop LAN IP, print a QR code in the terminal and show it on a laptop dashboard page.

## Phase 2 - Phone to Laptop
Mobile-friendly page with multi-file select, chunked upload (5 MB chunks) streamed to disk (never load a whole file in RAM, must handle 5 GB+), progress bar, speed, file size, cancel, retry failed chunks, resume after connection loss. Save to a configurable destination folder (default `./received`).

## Phase 3 - Laptop to Phone
Dashboard drag-and-drop to send files; phone sees a list and downloads with streaming and Range support; folder transfer as zip streamed on the fly.

## Phase 4 - Security
One-time PIN shown on laptop, QR contains a session token, device approval prompt on laptop, session timeout, device name display, path traversal protection, filename sanitizing. Add optional self-signed HTTPS via mkcert or the `cryptography` library, with a flag to enable it.

## Phase 5 - Polish
Transfer history (SQLite), dark mode, PWA manifest + service worker, file preview for images/videos, clean responsive UI, Android phone to iPhone support via the laptop web interface.

## Phase 6 - Packaging and deploy
a) `requirements.txt`, a run script, and a full README (setup, firewall tips, hotspot mode for no internet, iPhone limitations).
b) Dockerfile + docker-compose.yml (host networking note for LAN discovery).
c) PyInstaller build script producing a single Windows .exe and a macOS app/binary.
d) GitHub Actions workflow that builds the executables and attaches them to a GitHub Release on tag push.
e) Initialize git, add .gitignore, make clean commits per phase.
f) A simple static landing page (docs/ folder, GitHub Pages ready) with download links.
