import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Point every test at a throwaway dest/data/upload-tmp dir instead of
    the real ./received, so running the suite never touches real files."""
    settings.dest_dir = tmp_path / "received"
    settings.data_dir = tmp_path / "data"
    settings.upload_tmp_dir = tmp_path / "tmp_uploads"
    settings.lan_ip = "127.0.0.1"
    settings.port = 8000
    settings.require_pin = False
    settings.pin = ""
    settings.ensure_dirs()
    yield settings
