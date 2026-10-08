from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app


def client():
    return TestClient(create_app())


def test_full_chunked_upload_reassembles_file():
    c = client()
    payload = b"hello-world!" # 12 bytes
    init = c.post(
        "/api/upload/init",
        json={"filename": "report.pdf", "size": len(payload), "chunk_size": 4},
    ).json()
    assert init["total_chunks"] == 3
    upload_id = init["upload_id"]

    for i in range(3):
        chunk = payload[i * 4 : i * 4 + 4]
        resp = c.put(f"/api/upload/{upload_id}/chunk/{i}", content=chunk)
        assert resp.status_code == 200

    status = c.get(f"/api/upload/{upload_id}/status").json()
    assert status["complete"] is True
    assert status["missing"] == []

    done = c.post(f"/api/upload/{upload_id}/complete").json()
    final_path = settings.dest_dir / done["filename"]
    assert final_path.exists()
    assert final_path.read_bytes() == payload


def test_resume_reports_missing_chunks_and_completes():
    c = client()
    payload = b"0123456789abcdef"  # 16 bytes
    init = c.post(
        "/api/upload/init",
        json={"filename": "video.mp4", "size": len(payload), "chunk_size": 4},
    ).json()
    upload_id = init["upload_id"]

    c.put(f"/api/upload/{upload_id}/chunk/0", content=payload[0:4])
    c.put(f"/api/upload/{upload_id}/chunk/2", content=payload[8:12])

    status = c.get(f"/api/upload/{upload_id}/status").json()
    assert sorted(status["missing"]) == [1, 3]
    assert status["complete"] is False

    # simulate reconnect: client only resends the missing chunks
    c.put(f"/api/upload/{upload_id}/chunk/1", content=payload[4:8])
    c.put(f"/api/upload/{upload_id}/chunk/3", content=payload[12:16])

    status = c.get(f"/api/upload/{upload_id}/status").json()
    assert status["complete"] is True

    done = c.post(f"/api/upload/{upload_id}/complete").json()
    final_path = settings.dest_dir / done["filename"]
    assert final_path.read_bytes() == payload


def test_cancel_upload_removes_state_and_partial_file():
    c = client()
    init = c.post("/api/upload/init", json={"filename": "big.bin", "size": 8, "chunk_size": 4}).json()
    upload_id = init["upload_id"]
    c.put(f"/api/upload/{upload_id}/chunk/0", content=b"1234")

    resp = c.delete(f"/api/upload/{upload_id}")
    assert resp.status_code == 200

    assert c.get(f"/api/upload/{upload_id}/status").status_code == 404
    assert not any(settings.upload_tmp_dir.glob(f"{upload_id}.*"))


def test_filename_is_sanitized_on_init():
    c = client()
    init = c.post(
        "/api/upload/init",
        json={"filename": "../../evil.sh", "size": 4, "chunk_size": 4},
    ).json()
    assert init["filename"] == "evil.sh"

    c.put(f"/api/upload/{init['upload_id']}/chunk/0", content=b"test")
    done = c.post(f"/api/upload/{init['upload_id']}/complete").json()
    assert "/" not in done["filename"] and "\\" not in done["filename"]
    assert (settings.dest_dir / done["filename"]).resolve().parent == settings.dest_dir.resolve()


def test_unknown_upload_id_returns_404():
    c = client()
    assert c.get("/api/upload/does-not-exist/status").status_code == 404
    assert c.put("/api/upload/does-not-exist/chunk/0", content=b"x").status_code == 404
    assert c.post("/api/upload/does-not-exist/complete").status_code == 404
    assert c.delete("/api/upload/does-not-exist").status_code == 404


def test_chunk_index_out_of_range_returns_400():
    c = client()
    init = c.post("/api/upload/init", json={"filename": "a.txt", "size": 4, "chunk_size": 4}).json()
    resp = c.put(f"/api/upload/{init['upload_id']}/chunk/5", content=b"oops")
    assert resp.status_code == 400


def test_complete_before_all_chunks_received_returns_409():
    c = client()
    init = c.post("/api/upload/init", json={"filename": "a.txt", "size": 8, "chunk_size": 4}).json()
    resp = c.post(f"/api/upload/{init['upload_id']}/complete")
    assert resp.status_code == 409
