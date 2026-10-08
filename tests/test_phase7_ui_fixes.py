from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


def client():
    return TestClient(create_app())


def send_file(c, filename, payload, chunk_size=4):
    init = c.post("/api/send/init", json={"filename": filename, "size": len(payload), "chunk_size": chunk_size}).json()
    uid = init["upload_id"]
    for i in range(init["total_chunks"]):
        chunk = payload[i * chunk_size : i * chunk_size + chunk_size]
        c.put(f"/api/send/{uid}/chunk/{i}", content=chunk)
    return c.post(f"/api/send/{uid}/complete").json()


def test_outbox_ws_receives_push_on_send_complete():
    c = client()
    with c.websocket_connect("/ws/outbox") as ws:
        send_file(c, "note.txt", b"hello!!!")
        msg = ws.receive_json()
        assert msg["type"] == "outbox_changed"


def test_outbox_ws_receives_push_on_delete():
    c = client()
    send_file(c, "note.txt", b"hello!!!")
    item_id = c.get("/api/outbox").json()["files"][0]["item_id"]

    with c.websocket_connect("/ws/outbox") as ws:
        c.delete(f"/api/outbox/{item_id}")
        msg = ws.receive_json()
        assert msg["type"] == "outbox_changed"


def test_outbox_ws_receives_push_on_relay():
    settings.dest_dir.mkdir(parents=True, exist_ok=True)
    (settings.dest_dir / "photo.jpg").write_bytes(b"fake-bytes")
    c = client()

    with c.websocket_connect("/ws/outbox") as ws:
        c.post("/api/library/relay", params={"filename": "photo.jpg"})
        msg = ws.receive_json()
        assert msg["type"] == "outbox_changed"


def test_outbox_ws_requires_session_when_pin_enabled():
    settings.require_pin = True
    settings.pin = "111222"
    settings.qr_token = "ws-outbox-token"
    c = TestClient(create_app())

    import pytest
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with c.websocket_connect("/ws/outbox"):
            pass


def test_outbox_ws_allows_approved_session():
    settings.require_pin = True
    settings.pin = "333444"
    settings.qr_token = "ws-outbox-token2"
    c = TestClient(create_app())

    pair = c.post("/api/auth/pair", json={"pin": "333444", "device_name": "WS Phone"}).json()
    token = pair["pending_token"]
    c.post(f"/api/auth/approve/{token}")
    c.get(f"/api/auth/pair-status/{token}")  # sets the nd_session cookie on the client

    with c.websocket_connect("/ws/outbox") as ws:
        send_file(c, "secure.txt", b"secret!!")
        msg = ws.receive_json()
        assert msg["type"] == "outbox_changed"
