# PyInstaller spec for NaharDrop. Build with:
#   pyinstaller packaging/nahardrop.spec
# from the project root (see packaging/build_windows.ps1 / build_macos.sh).
#
# Bundles app/templates and app/static as data files, and the `qrcode`
# PNG-rendering path (which lazily imports PIL) plus uvicorn's protocol
# implementations, which PyInstaller's import scanner otherwise misses
# since they're only referenced from string-based factory lookups.
import sys
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH).parent

a = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "app" / "templates"), "app/templates"),
        (str(project_root / "app" / "static"), "app/static"),
    ],
    hiddenimports=[
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "PIL._tkinter_finder",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="nahardrop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)
