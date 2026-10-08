from fastapi.testclient import TestClient

from app.main import create_app
from app.network import get_lan_ip, make_qr_ascii, make_qr_png_base64


def test_get_lan_ip_returns_an_ip_like_string():
    ip = get_lan_ip()
    parts = ip.split(".")
    assert len(parts) == 4
    assert all(p.isdigit() for p in parts)


def test_make_qr_ascii_contains_block_characters():
    art = make_qr_ascii("http://192.168.1.10:8000/m")
    assert len(art) > 0


def test_make_qr_png_base64_is_a_data_uri():
    uri = make_qr_png_base64("http://192.168.1.10:8000/m")
    assert uri.startswith("data:image/png;base64,")


def test_dashboard_page_loads():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "NaharDrop" in resp.text
    assert "qr" in resp.text.lower()


def test_mobile_page_loads():
    app = create_app()
    client = TestClient(app)
    resp = client.get("/m")
    assert resp.status_code == 200
    assert "NaharDrop" in resp.text
