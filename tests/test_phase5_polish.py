from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


def client():
    return TestClient(create_app())


def test_upload_completion_is_recorded_in_history():
    c = client()
    payload = b"hello history"
    init = c.post("/api/upload/init", json={"filename": "memo.txt", "size": len(payload), "chunk_size": 4}).json()
    uid = init["upload_id"]
    for i in range(init["total_chunks"]):
        chunk = payload[i * 4 : i * 4 + 4]
        c.put(f"/api/upload/{uid}/chunk/{i}", content=chunk)
    c.post(f"/api/upload/{uid}/complete")

    history = c.get("/api/history").json()
    assert len(history) == 1
    assert history[0]["direction"] == "upload"
    assert history[0]["filename"] == "memo.txt"
    assert history[0]["size"] == len(payload)


def test_send_completion_is_recorded_in_history():
    c = client()
    init = c.post("/api/send/init", json={"filename": "clip.mp4", "size": 8, "chunk_size": 4}).json()
    uid = init["upload_id"]
    c.put(f"/api/send/{uid}/chunk/0", content=b"ABCD")
    c.put(f"/api/send/{uid}/chunk/1", content=b"EFGH")
    c.post(f"/api/send/{uid}/complete")

    history = c.get("/api/history").json()
    assert any(h["direction"] == "send" and h["filename"] == "clip.mp4" for h in history)


def test_received_listing_and_relay_to_outbox():
    settings.dest_dir.mkdir(parents=True, exist_ok=True)
    (settings.dest_dir / "photo.jpg").write_bytes(b"fake-jpeg-bytes")

    c = client()
    received = c.get("/api/library/received").json()
    assert any(f["filename"] == "photo.jpg" for f in received)

    relay = c.post("/api/library/relay", params={"filename": "photo.jpg"}).json()
    assert relay["filename"] == "photo.jpg"

    outbox = c.get("/api/outbox").json()
    assert any(f["name"] == "photo.jpg" for f in outbox["files"])

    item_id = next(f["item_id"] for f in outbox["files"] if f["name"] == "photo.jpg")
    resp = c.get(f"/api/outbox/file/{item_id}")
    assert resp.content == b"fake-jpeg-bytes"


def test_relay_rejects_path_traversal_and_missing_file():
    c = client()
    assert c.post("/api/library/relay", params={"filename": "does-not-exist.txt"}).status_code == 404
    assert c.post("/api/library/relay", params={"filename": "../../etc/passwd"}).status_code == 404


def test_preview_endpoint_uses_inline_disposition():
    c = client()
    init = c.post("/api/send/init", json={"filename": "pic.png", "size": 4, "chunk_size": 4}).json()
    uid = init["upload_id"]
    c.put(f"/api/send/{uid}/chunk/0", content=b"IMG!")
    c.post(f"/api/send/{uid}/complete")
    item_id = c.get("/api/outbox").json()["files"][0]["item_id"]

    resp = c.get(f"/api/outbox/file/{item_id}/preview")
    assert resp.status_code == 200
    assert "inline" in resp.headers["content-disposition"]


def test_manifest_and_service_worker_are_served():
    c = client()
    manifest = c.get("/static/manifest.json")
    assert manifest.status_code == 200
    assert manifest.json()["name"] == "NaharDrop"

    sw = c.get("/sw.js")
    assert sw.status_code == 200
    assert "application/javascript" in sw.headers["content-type"]
