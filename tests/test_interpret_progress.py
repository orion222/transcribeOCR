from scoreocr.stages.crop import run_crop
from scoreocr.stages.geometry import run_geometry
from scoreocr.stages.ingest import run_ingest
from scoreocr.stages.interpret import run_interpret
from scoreocr.workspace import Workspace
from tests.test_cli import StubInterpreter


def test_on_progress_reports_measure_counts(tmp_path, synthetic_page):
    ws = Workspace.create(tmp_path / "jobs")
    run_ingest(ws, [synthetic_page])
    run_geometry(ws)
    run_crop(ws)

    ticks = []
    run_interpret(ws, StubInterpreter(), on_progress=lambda d, t: ticks.append((d, t)))

    assert ticks, "on_progress was never called"
    done_values = [d for d, _ in ticks]
    totals = {t for _, t in ticks}
    assert len(totals) == 1 and totals.pop() > 0      # stable total
    assert done_values[-1] == max(done_values)         # monotonic-ish, ends at peak
    assert done_values[-1] <= ticks[-1][1]             # never exceeds total
