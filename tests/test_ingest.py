from PIL import Image

from scoreocr.stages.ingest import run_ingest
from scoreocr.workspace import Workspace


def _make_png(path, size=(400, 300)):
    Image.new("L", size, color=255).save(path)


def test_ingest_images_in_order(tmp_path):
    a, b = tmp_path / "b-page2.png", tmp_path / "a-page1.png"
    _make_png(a), _make_png(b)
    ws = Workspace.create(tmp_path / "jobs")
    run_ingest(ws, [b, a])  # explicit order wins, not filename sort
    state = ws.load_state()
    assert [p.page for p in state.pages] == ["p01", "p02"]
    assert state.pages[0].source_name == "a-page1.png"
    assert ws.source_path("p01").exists() and ws.source_path("p02").exists()
    assert state.status == "ingested"


def test_ingest_pdf(tmp_path):
    img = Image.new("L", (400, 300), color=255)
    pdf = tmp_path / "song.pdf"
    img.save(pdf, "PDF", resolution=72)
    ws = Workspace.create(tmp_path / "jobs")
    run_ingest(ws, [pdf])
    state = ws.load_state()
    assert len(state.pages) == 1
    out = Image.open(ws.source_path("p01"))
    assert out.width > 400  # rasterized above 72 dpi
