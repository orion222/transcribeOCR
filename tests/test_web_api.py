import io
import time

from fastapi.testclient import TestClient

from scoreocr.web.app import create_app
from tests.test_cli import StubInterpreter


def _png_bytes(path_drawer):
    buf = io.BytesIO()
    path_drawer().save(buf, format="PNG")
    return buf.getvalue()


def _client(tmp_path):
    app = create_app(tmp_path / "jobs", build_interpreter=StubInterpreter)
    return TestClient(app)


def _wait_complete(client, bid, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        m = client.get(f"/api/batches/{bid}").json()
        if m["status"] == "complete":
            return m
        time.sleep(0.1)
    raise AssertionError("batch did not complete in time")


def test_create_upload_start_snapshot(tmp_path):
    from tests.conftest import draw_page
    client = _client(tmp_path)

    bid = client.post("/api/batches", json={"self_check": False,
                                            "meta": {"title": "T"}}).json()["batch_id"]

    data = _png_bytes(draw_page)
    resp = client.post(
        f"/api/batches/{bid}/photos",
        files=[("files", ("p1.png", data, "image/png")),
               ("files", ("p2.png", data, "image/png"))],
    )
    assert resp.status_code == 200
    assert [p["order"] for p in resp.json()["photos"]] == [1, 2]

    assert client.post(f"/api/batches/{bid}/start").status_code == 200
    final = _wait_complete(client, bid)
    assert [p["status"] for p in final["photos"]] == ["done", "done"]


def test_events_stream_reports_completion(tmp_path):
    from tests.conftest import draw_page
    client = _client(tmp_path)
    bid = client.post("/api/batches", json={}).json()["batch_id"]
    data = _png_bytes(draw_page)
    client.post(f"/api/batches/{bid}/photos",
                files=[("files", ("p1.png", data, "image/png"))])
    client.post(f"/api/batches/{bid}/start")

    lines = []
    with client.stream("GET", f"/api/batches/{bid}/events") as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            lines.append(line)
            if '"status": "complete"' in line or '"status":"complete"' in line:
                break
    body = "\n".join(lines)
    assert "snapshot" in body
    assert "complete" in body


def test_events_stream_ends_for_already_complete_batch(tmp_path):
    from tests.conftest import draw_page
    client = _client(tmp_path)
    bid = client.post("/api/batches", json={}).json()["batch_id"]
    data = _png_bytes(draw_page)
    client.post(f"/api/batches/{bid}/photos",
                files=[("files", ("p1.png", data, "image/png"))])
    client.post(f"/api/batches/{bid}/start")
    _wait_complete(client, bid)  # batch fully done BEFORE we subscribe

    lines = []
    with client.stream("GET", f"/api/batches/{bid}/events") as r:
        assert r.status_code == 200
        for line in r.iter_lines():   # MUST terminate (would hang forever without the fix)
            lines.append(line)
    body = "\n".join(lines)
    assert "snapshot" in body
    assert "complete" in body


def test_assets_merge_and_download(tmp_path):
    from tests.conftest import draw_page
    client = _client(tmp_path)
    bid = client.post("/api/batches", json={}).json()["batch_id"]
    data = _png_bytes(draw_page)
    client.post(f"/api/batches/{bid}/photos",
                files=[("files", ("p1.png", data, "image/png")),
                       ("files", ("p2.png", data, "image/png"))])
    client.post(f"/api/batches/{bid}/start")
    final = _wait_complete(client, bid)
    pid = final["photos"][0]["photo_id"]

    xml = client.get(f"/api/batches/{bid}/photos/{pid}/musicxml")
    assert xml.status_code == 200 and b"score-partwise" in xml.content

    svgs = client.get(f"/api/batches/{bid}/photos/{pid}/preview").json()["svgs"]
    assert svgs and "<svg" in svgs[0]

    midi = client.get(f"/api/batches/{bid}/photos/{pid}/midi")
    assert midi.status_code == 200 and midi.content[:4] == b"MThd"

    merged = client.post(f"/api/batches/{bid}/merge")
    assert merged.status_code == 200 and merged.json()["svg_count"] >= 1
    mx = client.get(f"/api/batches/{bid}/merged/musicxml")
    assert b"score-partwise" in mx.content


def test_retry_reprocesses_and_recomputes_complete(tmp_path):
    from tests.conftest import draw_page
    client = _client(tmp_path)
    bid = client.post("/api/batches", json={}).json()["batch_id"]
    data = _png_bytes(draw_page)
    client.post(f"/api/batches/{bid}/photos",
                files=[("files", ("p1.png", data, "image/png"))])
    client.post(f"/api/batches/{bid}/start")
    _wait_complete(client, bid)

    pid = client.get(f"/api/batches/{bid}").json()["photos"][0]["photo_id"]
    r = client.post(f"/api/batches/{bid}/photos/{pid}/retry")
    assert r.status_code == 200 and r.json()["status"] == "processing"

    final = _wait_complete(client, bid)   # recomputed back to complete after retry
    assert final["photos"][0]["status"] == "done"


def test_root_serves_spa_when_built(tmp_path, monkeypatch):
    # simulate a built frontend
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>spa</title>")
    monkeypatch.setenv("SCOREOCR_FRONTEND_DIST", str(dist))

    app = create_app(tmp_path / "jobs", build_interpreter=StubInterpreter)
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200 and "spa" in r.text
