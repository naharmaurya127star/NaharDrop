# NaharDrop

Send files between your phone and laptop over your own Wi-Fi. No cloud, no
cables, no account, no size limit beyond your disk. Works between any
combination of Android and iPhone, because both talk to the laptop's
browser-based web interface rather than to each other.

## Quickstart

```bash
pip install -r requirements.txt
python run.py
```

Or use the convenience launcher, which creates a venv and installs
dependencies for you on first run:

- Windows: `run.bat`
- macOS/Linux: `./run.sh`

The terminal prints a QR code and a PIN. Scan the QR with your phone's
camera (same Wi-Fi network as the laptop), or type the printed URL into the
phone's browser and enter the PIN. Either way, approve the device on the
laptop's dashboard when prompted - then drag files onto the dashboard to
send them to the phone, or use the phone's "Send to laptop" tab to send
files the other way.

## First run on Windows

- **SmartScreen warning:** the downloaded `nahardrop-windows-x64.exe` isn't code-signed, so Windows may show "Windows protected your PC". Click **More info**, then **Run anyway**.
- **Firewall:** when Windows asks about Python or `nahardrop.exe`, allow access on **Private networks**. Public networks are blocked on purpose, since your phone is on the same home or hotspot network.
- **Same Wi-Fi:** the phone must be on the same Wi-Fi network as the laptop. Guest networks and some public Wi-Fi isolate devices from each other, so use your home network or a phone hotspot instead.

## CLI flags

| Flag | Default | Meaning |
|---|---|---|
| `--host` | `0.0.0.0` | Bind address |
| `--port` | `8000` | Bind port |
| `--dest` | `./received` | Where files uploaded from a phone are saved |
| `--https` | off | Serve over HTTPS (self-signed unless `--cert-file`/`--key-file` given) |
| `--cert-file`, `--key-file` | - | Use your own certificate (e.g. from `mkcert`) instead of an auto-generated one |
| `--no-pin` | off | Disable the PIN/device-approval gate entirely (open LAN access) |
| `--advertise-ip` | auto-detected | Override the IP shown in the QR/URL (needed in Docker without host networking) |

## Firewall tips

The first time you run NaharDrop, your OS firewall will likely prompt you
to allow incoming connections on the chosen port:

- **Windows**: allow Python (or the packaged `nahardrop.exe`) on "Private
  networks" when Windows Defender Firewall prompts you. If you don't get a
  prompt, add a rule manually: Windows Defender Firewall > Advanced
  Settings > Inbound Rules > New Rule > Port > TCP > `8000`.
- **macOS**: System Settings > Network > Firewall > allow incoming
  connections for Python/nahardrop when prompted.
- **Linux**: `sudo ufw allow 8000/tcp` (adjust the port if you changed it).

If your phone can load the QR image on the dashboard but the resulting URL
times out, it's almost always this firewall prompt being missed or denied.

## Hotspot mode (no internet available)

NaharDrop never needs internet access - it only needs your phone and
laptop on the *same* local network. If there's no Wi-Fi router available:

1. Turn your **phone** into a Wi-Fi hotspot and connect your **laptop** to
   it, or turn your **laptop** into a hotspot and connect your **phone** to
   it (Windows: Settings > Network > Mobile hotspot; macOS: System Settings
   > Sharing > Internet Sharing).
2. Run NaharDrop as usual - LAN IP auto-detection picks up whichever
   interface has a route, which will be the hotspot link.
3. Scan the QR / open the URL as normal.

## iPhone / Safari limitations

- Safari's file picker supports selecting multiple files, but **not**
  picking a whole folder (unlike the laptop dashboard's folder drag-drop).
  Each file uploads individually from an iPhone, same as from Android.
- iOS aggressively suspends background tabs. If you switch away from Safari
  mid-upload, the upload may pause; switching back resumes it from the last
  completed chunk (Phase 2's resume logic), it won't silently fail, but it
  also won't continue progressing while the tab isn't frontmost.
- "Add to Home Screen" (the PWA manifest) gives you an app-like icon and
  standalone window, but iOS Safari does not support background sync or
  push notifications for PWAs the way Android Chrome does.
- Video preview scrubbing relies on HTTP Range requests, which Safari
  supports fine for files served by NaharDrop.

## Docker

```bash
docker compose up --build
```

LAN IP auto-detection only makes sense if the container can see your real
network interface:

- **Linux**: `docker-compose.yml` uses `network_mode: host` by default,
  which works out of the box.
- **macOS/Windows (Docker Desktop)**: host networking isn't supported the
  same way. Comment out `network_mode: host`, uncomment the `ports:` block,
  and set `NAHARDROP_ADVERTISE_IP` to your machine's actual LAN IP (e.g.
  `192.168.1.23`) so the QR code points phones at a reachable address
  instead of the container's internal one.

Received files land in `./received` and app data (history DB, outbox,
generated TLS cert) in `./data`, both bind-mounted from the project
directory so they survive container restarts.

## Packaging a standalone executable

```bash
pip install pyinstaller
# Windows:
.\venv\Scripts\Activate.ps1
.\packaging\build_windows.ps1
# macOS:
source venv/bin/activate
./packaging/build_macos.sh
```

Produces a single `dist/nahardrop(.exe)` with no Python install required on
the target machine. Double-click it (or run from a terminal to see the
QR/PIN) and it behaves exactly like `python run.py`.

## Cutting a GitHub release

Pushing a tag matching `v*.*.*` triggers `.github/workflows/release.yml`,
which builds both the Windows `.exe` and macOS binary on their native
runners and attaches them to a new GitHub Release automatically:

```bash
git tag v1.0.0
git push origin v1.0.0
```

## GitHub Pages landing page

`docs/index.html` is a static landing page with download buttons pointed at
`<repo>/releases/latest/download/...`. Enable it in your repo's Settings >
Pages > "Deploy from a branch" > branch `main`, folder `/docs`.

## Running the tests

```bash
pip install pytest httpx
pytest
```

Covers chunked upload/resume/cancel, path traversal and filename
sanitizing, folder-zip streaming, Range requests, PIN/QR pairing and device
approval, session gating, TLS cert generation, history recording, and the
received-to-outbox relay.

## How it's built (decisions worth knowing)

- **Single process.** Upload progress, pending-device approval, and
  sessions all live in memory (not a database or external cache), so
  NaharDrop always runs as one uvicorn worker. This is a personal LAN tool
  for one laptop, not a multi-tenant service - simplicity won over
  horizontal scalability that nothing here needs.
- **Chunked upload in both directions.** Phone-to-laptop (Phase 2) and the
  dashboard's drag-and-drop send (Phase 3) both go through the same chunked
  engine (`app/uploads.py`, `static/js/chunked-uploader.js`): a chunk lands
  at its byte offset in a pre-sized `.part` file, with a JSON manifest
  tracking which chunk indices arrived, so a dropped connection resumes by
  re-sending only what's missing - without ever holding a whole file (or
  even a whole chunk beyond the network read size) in memory.
- **Cookie-based sessions.** After laptop approval, the phone gets an
  HttpOnly cookie rather than a bearer token, specifically so plain
  `<a download>` links (used for native, memory-safe multi-GB downloads)
  carry auth automatically - a header-based token wouldn't attach to a bare
  link click.
- **Two pairing paths, one approval gate.** Scanning the dashboard's QR
  carries a one-time `qr_token` in the URL and skips the PIN prompt; typing
  the URL manually requires the PIN shown on the laptop. Either way, the
  laptop operator still approves the device before it's granted a session -
  this is enforced in `app/routes/auth.py`, not just in the UI.
- **History is "sent", not "confirmed delivered".** A streaming download
  response has no reliable "the phone actually got all the bytes" signal,
  so Transfer History records when a file *became available* (upload/send
  completed), not when a download finished.
- **The "Android to iPhone" story** is just the laptop in the middle: one
  phone uploads to `./received`, the dashboard's "Send to phone" button
  relays that file into the outbox, a second phone downloads it. Neither
  phone ever talks to the other directly, so the only requirement is that
  both can reach the laptop's browser interface.
- **Zip streaming** for folder downloads uses `zipstream-ng`, which
  generates the archive on the fly (stored, not compressed, since LAN
  transfers are rarely CPU-bound) so a multi-GB folder never has to exist as
  a zip on disk or in memory before it starts downloading.

## Project structure

```
app/
  main.py          FastAPI app factory + terminal startup banner
  config.py        Settings singleton (host/port/dest/security/etc.)
  network.py       LAN IP detection, QR rendering
  security.py      Filename/path sanitizing, PIN/session/device-approval store
  uploads.py       Chunked upload engine (used by both directions)
  outbox.py        Files queued for the phone to download
  history.py       SQLite transfer history
  tls.py           Self-signed HTTPS certificate generation
  ws.py            Dashboard WebSocket push (pending devices, etc.)
  routes/          HTTP/WebSocket routes, one module per concern
  templates/       Jinja2 pages (dashboard, mobile)
  static/          CSS/JS/manifest/service worker/icons
run.py             CLI entry point
tests/             pytest suite
packaging/         PyInstaller spec + build scripts
docs/              GitHub Pages landing page
```
