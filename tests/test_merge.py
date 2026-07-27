# tests/test_merge.py
from lxml import etree as ET

from scoreocr.pipeline import run_pipeline
from scoreocr.web.batch import BatchStore
from scoreocr.web.merge import merge_batch
from tests.test_cli import StubInterpreter


def _print_attrs(root, number):
    """Get the attributes dict of the <print> child of a measure by number."""
    for mm in root.iter("measure"):
        if int(mm.get("number")) == number:
            pr = mm.find("print")
            return dict(pr.attrib) if pr is not None else {}
    raise AssertionError(f"measure {number} not found")


def _process(store, batch_id, ref):
    ws = store.workspace(batch_id, ref.job_id)
    run_pipeline(ws, StubInterpreter(), [store.input_path(batch_id, ref)])
    m = store.load(batch_id)
    next(p for p in m.photos if p.photo_id == ref.photo_id).status = "done"
    store.save(m)


def test_merge_renumbers_and_concatenates(tmp_path, synthetic_page):
    data = synthetic_page.read_bytes()
    store = BatchStore(tmp_path / "jobs")
    m = store.create()
    r1 = store.add_photo(m.batch_id, "p1.png", data, ".png")
    r2 = store.add_photo(m.batch_id, "p2.png", data, ".png")
    _process(store, m.batch_id, r1)
    _process(store, m.batch_id, r2)

    out = merge_batch(store, m.batch_id)
    assert out.exists()
    root = ET.fromstring(out.read_bytes())
    numbers = [int(mm.get("number")) for mm in root.iter("measure")]
    # synthetic page = 2 systems x 4 measures = 8 per photo, 16 merged, 1..16
    assert numbers == list(range(1, 17))

    # Verify page/system break placement in merged score
    assert _print_attrs(root, 1) == {}                       # global first: no break
    assert _print_attrs(root, 5).get("new-system") == "yes"  # photo 1, system 2
    assert _print_attrs(root, 9).get("new-page") == "yes"    # photo 2 starts a page
    assert _print_attrs(root, 13).get("new-system") == "yes" # photo 2, system 2

    assert list((store.merged_dir(m.batch_id) / "preview").glob("*.svg"))


def test_merge_requires_a_done_photo(tmp_path, synthetic_page):
    store = BatchStore(tmp_path / "jobs")
    m = store.create()
    store.add_photo(m.batch_id, "p1.png", synthetic_page.read_bytes(), ".png")
    try:
        merge_batch(store, m.batch_id)
        assert False, "expected ValueError"
    except ValueError:
        pass
