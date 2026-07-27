import json

from PIL import Image

from scoreocr.pipeline import run_pipeline
from scoreocr.workspace import Workspace
from tests.test_cli import StubInterpreter


def test_run_pipeline_success_and_progress(tmp_path, synthetic_page):
    ws = Workspace.create(tmp_path / "jobs")
    seen = []
    result = run_pipeline(
        ws, StubInterpreter(), [synthetic_page],
        on_progress=lambda ev: seen.append(ev.stage),
    )
    assert result.status == "done"
    assert (ws.output_dir / "score.musicxml").exists()
    assert list((ws.output_dir / "preview").glob("*.svg"))
    # stages reported, in order, terminating in "done"
    for expected in ["ingest", "geometry", "crop", "interpret", "assemble",
                     "validate", "render", "done"]:
        assert expected in seen
    assert seen[-1] == "done"
    assert json.loads((ws.root / "job.json").read_text())["status"] == "done"


def test_run_pipeline_stage_failure_is_captured(tmp_path):
    ws = Workspace.create(tmp_path / "jobs")
    blank = tmp_path / "blank.png"
    Image.new("L", (400, 300), color=255).save(blank)  # no staff lines
    result = run_pipeline(ws, StubInterpreter(), [blank])
    assert result.status == "failed:geometry"
    assert result.error
    assert json.loads((ws.root / "job.json").read_text())["status"] == "failed:geometry"
