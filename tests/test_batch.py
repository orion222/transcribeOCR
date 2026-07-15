from scoreocr.models import ScoreMeta
from scoreocr.web.batch import BatchStore


def test_create_and_add_photos_are_ordered(tmp_path):
    store = BatchStore(tmp_path / "jobs")
    m = store.create(self_check=True, meta_overrides={"title": "Etude"})
    assert m.batch_id.startswith("batch-")
    assert m.self_check is True

    a = store.add_photo(m.batch_id, "a.png", b"AAA", ".png")
    b = store.add_photo(m.batch_id, "b.png", b"BBB", ".png")
    assert (a.order, b.order) == (1, 2)
    assert a.photo_id == "ph01" and b.photo_id == "ph02"

    reloaded = store.load(m.batch_id)
    assert [p.source_name for p in reloaded.photos] == ["a.png", "b.png"]

    # input bytes are written where the pipeline can ingest them
    assert store.input_path(m.batch_id, a).read_bytes() == b"AAA"

    # meta overrides seed score-meta.json in each photo workspace
    ws = store.workspace(m.batch_id, a.job_id)
    seeded = ScoreMeta.model_validate_json(ws.score_meta_path.read_text())
    assert seeded.title == "Etude"


def test_no_overrides_leaves_meta_unseeded(tmp_path):
    store = BatchStore(tmp_path / "jobs")
    m = store.create()
    ref = store.add_photo(m.batch_id, "a.png", b"AAA", ".png")
    ws = store.workspace(m.batch_id, ref.job_id)
    assert not ws.score_meta_path.exists()
