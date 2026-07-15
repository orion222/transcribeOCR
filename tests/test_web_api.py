import io
import time

from fastapi.testclient import TestClient
from PIL import Image

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
