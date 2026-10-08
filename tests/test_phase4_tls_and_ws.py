from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app
from app.tls import ensure_self_signed_cert


def test_ensure_self_signed_cert_creates_and_reuses_files(tmp_path):
    cert1, key1 = ensure_self_signed_cert(tmp_path, "192.168.1.10")
    assert cert1.exists() and key1.exists()
    assert cert1.read_bytes().startswith(b"-----BEGIN CERTIFICATE-----")
    assert key1.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----") or b"PRIVATE KEY" in key1.read_bytes()

    cert2, key2 = ensure_self_signed_cert(tmp_path, "192.168.1.10")
    assert cert1 == cert2 and key1 == key2  # cached, not regenerated


def test_dashboard_websocket_receives_pending_device_broadcast():
    settings.require_pin = True
    settings.pin = "654321"
    settings.qr_token = "ws-test-token"
    app = create_app()
    client = TestClient(app)

    with client.websocket_connect("/api/auth/ws/dashboard") as ws:
        client.post("/api/auth/pair", json={"pin": "654321", "device_name": "WS Phone"})
        msg = ws.receive_json()
        assert msg["type"] == "pending_device"
        assert msg["device_name"] == "WS Phone"
