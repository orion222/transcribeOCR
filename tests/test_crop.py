from PIL import Image

from scoreocr.stages.geometry import run_geometry
from scoreocr.stages.crop import crop_paths, run_crop
from scoreocr.stages.ingest import run_ingest
from scoreocr.workspace import Workspace


def _prepared_ws(tmp_path, synthetic_page):
    ws = Workspace.create(tmp_path / "jobs")
    run_ingest(ws, [synthetic_page])
    run_geometry(ws)
    return ws


def test_crop_writes_all_measures(tmp_path, synthetic_page):
    ws = _prepared_ws(tmp_path, synthetic_page)
    run_crop(ws)
    paths = crop_paths(ws, "p01")
    assert len(paths["systems"]) == 2
    assert sorted(paths["measures"]) == list(range(1, 9))
    m1 = Image.open(paths["measures"][1])
    assert m1.width > 100 and m1.height > 100


def test_crop_status(tmp_path, synthetic_page):
    ws = _prepared_ws(tmp_path, synthetic_page)
    run_crop(ws)
    assert ws.load_state().status == "cropped"
