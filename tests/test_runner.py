from scoreocr.web.batch import BatchStore
from scoreocr.web.broker import EventBroker
from scoreocr.web.runner import run_batch
from tests.test_cli import StubInterpreter


def test_run_batch_processes_all_photos_and_completes(tmp_path, synthetic_page):
    data = synthetic_page.read_bytes()
    store = BatchStore(tmp_path / "jobs")
    m = store.create()
    store.add_photo(m.batch_id, "p1.png", data, ".png")
    store.add_photo(m.batch_id, "p2.png", data, ".png")

    events = []
    broker = EventBroker()
    broker.publish = lambda bid, ev: events.append((bid, ev))  # capture synchronously

    run_batch(store, broker, m.batch_id, build_interpreter=StubInterpreter)

    final = store.load(m.batch_id)
    assert final.status == "complete"
    assert [p.status for p in final.photos] == ["done", "done"]
    assert ("photo" in {ev["type"] for _, ev in events})
    assert events[-1][1] == {"type": "batch", "status": "complete"}
    # each done photo has a real score file
    for p in final.photos:
        ws = store.workspace(m.batch_id, p.job_id)
        assert (ws.output_dir / "score.musicxml").exists()


def test_run_batch_isolates_photo_failure(tmp_path, synthetic_page):
    from PIL import Image
    store = BatchStore(tmp_path / "jobs")
    m = store.create()
    blank = tmp_path / "blank.png"
    Image.new("L", (400, 300), color=255).save(blank)
    store.add_photo(m.batch_id, "bad.png", blank.read_bytes(), ".png")
    store.add_photo(m.batch_id, "good.png", synthetic_page.read_bytes(), ".png")

    broker = EventBroker()  # no loop bound -> publish is a safe no-op
    run_batch(store, broker, m.batch_id, build_interpreter=StubInterpreter)

    final = store.load(m.batch_id)
    assert final.status == "complete"
    assert final.photos[0].status == "failed:geometry"
    assert final.photos[0].error
    assert final.photos[1].status == "done"
