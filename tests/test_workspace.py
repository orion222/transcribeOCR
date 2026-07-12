from scoreocr.models import JobState, PageEntry
from scoreocr.workspace import Workspace


def test_create_and_reload(tmp_path):
    ws = Workspace.create(tmp_path)
    assert (ws.root / "job.json").exists()
    ws2 = Workspace(ws.root)
    assert ws2.load_state().job_id == ws.job_id


def test_state_roundtrip(tmp_path):
    ws = Workspace.create(tmp_path)
    state = ws.load_state()
    state.status = "geometry"
    state.pages = [PageEntry(page="p01", source_name="a.png", measure_start=1, measure_end=24)]
    ws.save_state(state)
    assert ws.load_state().status == "geometry"


def test_measure_ir_path_maps_to_page(tmp_path):
    ws = Workspace.create(tmp_path)
    state = ws.load_state()
    state.pages = [
        PageEntry(page="p01", source_name="a.png", measure_start=1, measure_end=24),
        PageEntry(page="p02", source_name="b.png", measure_start=25, measure_end=52),
    ]
    ws.save_state(state)
    p = ws.measure_ir_path(30)
    assert "p02" in str(p) and p.name == "m030.json"
