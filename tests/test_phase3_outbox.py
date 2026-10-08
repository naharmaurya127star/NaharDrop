import zipfile
from io import BytesIO

from fastapi.testclient import TestClient

from app.main import create_app


def client():
    return TestClient(create_app())


def send_file(c, filename, payload, chunk_size=4, rel_dir=None, group=None):
    init = c.post(
        "/api/send/init",
        json={"filename": filename, "size": len(payload), "chunk_size": chunk_size, "rel_dir": rel_dir},
    ).json()
    upload_id = init["upload_id"]
    for i in range(init["total_chunks"]):
        chunk = payload[i * chunk_size : i * chunk_size + chunk_size]
        c.put(f"/api/send/{upload_id}/chunk/{i}", content=chunk)
    params = {"group": group} if group else {}
    return c.post(f"/api/send/{upload_id}/complete", params=params).json()


def test_send_flat_file_appears_in_outbox_and_downloads():
    c = client()
    payload = b"dashboard-dropped-file!"
    send_file(c, "notes.txt", payload)

    listing = c.get("/api/outbox").json()
    assert len(listing["files"]) == 1
    item_id = listing["files"][0]["item_id"]
    assert listing["files"][0]["size"] == len(payload)

    resp = c.get(f"/api/outbox/file/{item_id}")
    assert resp.status_code == 200
    assert resp.content == payload
    assert "attachment" in resp.headers["content-disposition"]


def test_range_request_returns_partial_content():
    c = client()
    payload = bytes(range(256)) * 4  # 1024 bytes, easy to slice and verify
    send_file(c, "data.bin", payload, chunk_size=128)
    item_id = c.get("/api/outbox").json()["files"][0]["item_id"]

    resp = c.get(f"/api/outbox/file/{item_id}", headers={"Range": "bytes=10-19"})
    assert resp.status_code == 206
    assert resp.content == payload[10:20]
    assert resp.headers["content-range"] == f"bytes 10-19/{len(payload)}"

    full = c.get(f"/api/outbox/file/{item_id}")
    assert full.headers["accept-ranges"] == "bytes"


def test_folder_drop_groups_files_and_streams_zip():
    c = client()
    send_file(c, "a.txt", b"AAAA", rel_dir="myfolder", group="myfolder")
    send_file(c, "b.txt", b"BBBBBBBB", rel_dir="myfolder/sub", group="myfolder")

    listing = c.get("/api/outbox").json()
    assert listing["files"] == []
    assert len(listing["folders"]) == 1
    folder = listing["folders"][0]
    assert folder["group"] == "myfolder"
    assert folder["count"] == 2
    assert folder["size"] == 12

    resp = c.get("/api/outbox/folder/myfolder/zip")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(BytesIO(resp.content))
    names = set(zf.namelist())
    assert "myfolder/a.txt" in names
    assert "myfolder/sub/b.txt" in names
    assert zf.read("myfolder/a.txt") == b"AAAA"
    assert zf.read("myfolder/sub/b.txt") == b"BBBBBBBB"


def test_download_unknown_item_and_unknown_folder_404():
    c = client()
    assert c.get("/api/outbox/file/does-not-exist").status_code == 404
    assert c.get("/api/outbox/folder/does-not-exist/zip").status_code == 404


def test_delete_outbox_item():
    c = client()
    send_file(c, "temp.txt", b"bye")
    item_id = c.get("/api/outbox").json()["files"][0]["item_id"]

    assert c.delete(f"/api/outbox/{item_id}").status_code == 200
    assert c.get("/api/outbox").json()["files"] == []
    assert c.get(f"/api/outbox/file/{item_id}").status_code == 404
