from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


def secured_client():
    settings.require_pin = True
    settings.pin = "123456"
    settings.qr_token = "test-qr-token"
    return TestClient(create_app())


def test_protected_routes_require_session_when_pin_enabled():
    c = secured_client()
    assert c.get("/api/outbox").status_code == 401
    assert c.post("/api/upload/init", json={"filename": "a.txt", "size": 4}).status_code == 401


def test_pair_with_wrong_pin_rejected():
    c = secured_client()
    resp = c.post("/api/auth/pair", json={"pin": "000000", "device_name": "Test Phone"})
    assert resp.status_code == 401


def test_pair_approve_flow_grants_session_cookie():
    c = secured_client()
    pair = c.post("/api/auth/pair", json={"pin": "123456", "device_name": "Test Phone"}).json()
    token = pair["pending_token"]

    # not approved yet
    status = c.get(f"/api/auth/pair-status/{token}").json()
    assert status["status"] == "pending"
    assert c.get("/api/outbox").status_code == 401

    pending = c.get("/api/auth/pending").json()
    assert any(p["token"] == token and p["device_name"] == "Test Phone" for p in pending)

    approve = c.post(f"/api/auth/approve/{token}").json()
    assert approve["approved"] is True

    status = c.get(f"/api/auth/pair-status/{token}").json()
    assert status["status"] == "approved"

    # the cookie set by pair-status should now authorize protected routes
    assert c.get("/api/outbox").status_code == 200

    sessions = c.get("/api/auth/sessions").json()
    assert any(s["device_name"] == "Test Phone" for s in sessions)


def test_pair_deny_flow_blocks_access():
    c = secured_client()
    pair = c.post("/api/auth/pair", json={"pin": "123456", "device_name": "Rejected Phone"}).json()
    token = pair["pending_token"]

    deny = c.post(f"/api/auth/deny/{token}").json()
    assert deny["denied"] is True

    status = c.get(f"/api/auth/pair-status/{token}").json()
    assert status["status"] == "denied"
    assert c.get("/api/outbox").status_code == 401


def test_pair_via_qr_token():
    c = secured_client()
    pair = c.post("/api/auth/pair", json={"token": "test-qr-token", "device_name": "QR Phone"}).json()
    token = pair["pending_token"]
    c.post(f"/api/auth/approve/{token}")
    status = c.get(f"/api/auth/pair-status/{token}").json()
    assert status["status"] == "approved"
    assert c.get("/api/outbox").status_code == 200


def test_unauthenticated_routes_work_when_pin_disabled():
    settings.require_pin = False
    c = TestClient(create_app())
    assert c.get("/api/outbox").status_code == 200
    resp = c.post("/api/auth/pair", json={"pin": "123456"})
    assert resp.status_code == 400
