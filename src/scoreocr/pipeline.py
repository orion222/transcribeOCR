from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from scoreocr.models import ScoreMeta
from scoreocr.stages.assemble import run_assemble
from scoreocr.stages.crop import run_crop
from scoreocr.stages.geometry import run_geometry
from scoreocr.stages.ingest import run_ingest
from scoreocr.stages.interpret import run_interpret
from scoreocr.stages.render import run_render
from scoreocr.stages.selfcheck import run_selfcheck
from scoreocr.stages.validate import validate_musicxml
from scoreocr.workspace import Workspace


@dataclass
class ProgressEvent:
    stage: str
    measures_done: int = 0
    measures_total: int = 0


@dataclass
class PipelineResult:
    status: str
    issues: list = field(default_factory=list)
    error: str | None = None


ProgressCallback = Callable[[ProgressEvent], None]


def run_pipeline(
    ws: Workspace,
    interpreter,
    inputs: list[Path],
    *,
    self_check: bool = False,
    max_workers: int = 4,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    def emit(stage: str, done: int = 0, total: int = 0) -> None:
        if on_progress is not None:
            on_progress(ProgressEvent(stage, done, total))

    state = ws.load_state()
    state.self_check = self_check
    state.error = None
    ws.save_state(state)

    stage = "startup"
    issues: list = []
    try:
        stage = "ingest"; emit(stage)
        run_ingest(ws, inputs)
        stage = "geometry"; emit(stage)
        run_geometry(ws)
        stage = "crop"; emit(stage)
        run_crop(ws)
        stage = "interpret"; emit(stage)
        run_interpret(
            ws, interpreter, max_workers=max_workers,
            on_progress=lambda d, t: emit("interpret", d, t),
        )
        stage = "assemble"; emit(stage)
        run_assemble(ws)

        stage = "validate"; emit(stage)
        meta = ScoreMeta.model_validate_json(ws.score_meta_path.read_text())
        state = ws.load_state()
        expected = list(
            range(state.pages[0].measure_start, state.pages[-1].measure_end + 1)
        )
        issues = validate_musicxml(
            (ws.output_dir / "score.musicxml").read_bytes(), meta, expected
        )

        stage = "render"; emit(stage)
        run_render(ws)
        if self_check:
            stage = "selfcheck"; emit(stage)
            run_selfcheck(ws, interpreter)
    except Exception as exc:
        state = ws.load_state()
        state.status = f"failed:{stage}"
        state.error = str(exc)
        ws.save_state(state)
        return PipelineResult(status=f"failed:{stage}", issues=issues, error=str(exc))

    state = ws.load_state()
    state.status = "done"
    ws.save_state(state)
    emit("done")
    return PipelineResult(status="done", issues=issues)
