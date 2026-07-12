import io
from typing import Literal

import cairosvg
from PIL import Image
from pydantic import BaseModel

from scoreocr.claude.interpreter import Interpreter
from scoreocr.models import MeasureIR, PageGeometry, ScoreMeta
from scoreocr.stages.assemble import run_assemble
from scoreocr.stages.crop import crop_paths
from scoreocr.stages.interpret import run_interpret
from scoreocr.stages.render import render_file, run_render
from scoreocr.stages.serialize import to_musicxml
from scoreocr.workspace import Workspace


class Discrepancy(BaseModel):
    measure: int
    staff: Literal["treble", "bass"]
    description: str


class DiscrepancyReport(BaseModel):
    discrepancies: list[Discrepancy]


def _render_system_png(ws: Workspace, meta: ScoreMeta, numbers: list[int]) -> Image.Image:
    measures = [
        MeasureIR.model_validate_json(ws.measure_ir_path(n).read_text())
        for n in numbers
        if ws.measure_ir_path(n).exists()
    ]
    xml = to_musicxml(meta, measures)
    tmp = ws.output_dir / "_selfcheck.musicxml"
    tmp.write_bytes(xml)
    svgs = render_file(tmp, ws.output_dir / "_selfcheck", "system")
    png = cairosvg.svg2png(bytestring=svgs[0].read_bytes())
    return Image.open(io.BytesIO(png))


def run_selfcheck(ws: Workspace, interpreter: Interpreter, *, max_rounds: int = 2) -> list[Discrepancy]:
    meta = ScoreMeta.model_validate_json(ws.score_meta_path.read_text())
    # Reset interpreter's reinterpreted tracking to record only selfcheck re-runs
    if hasattr(interpreter, 'reinterpreted'):
        interpreter.reinterpreted = []
    remaining: list[Discrepancy] = []
    for _ in range(max_rounds):
        state = ws.load_state()
        remaining = []
        for entry in state.pages:
            geo = PageGeometry.model_validate_json(ws.geometry_path(entry.page).read_text())
            paths = crop_paths(ws, entry.page)
            for si, system in enumerate(geo.systems):
                source = Image.open(paths["systems"][si])
                rendered = _render_system_png(ws, meta, system.measure_numbers)
                report, usage = interpreter.compare_images(
                    source, rendered, system.measure_numbers)
                state.input_tokens += usage["input_tokens"]
                state.output_tokens += usage["output_tokens"]
                remaining.extend(report.discrepancies)
        ws.save_state(state)
        if not remaining:
            break
        feedback = {
            d.measure: f"Self-check ({d.staff}): {d.description}" for d in remaining
        }
        run_interpret(ws, interpreter, only_measures=set(feedback), feedback=feedback)
        run_assemble(ws)
        run_render(ws)
    state = ws.load_state()
    state.status = "selfchecked"
    ws.save_state(state)
    return remaining
