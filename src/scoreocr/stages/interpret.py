import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from scoreocr.claude.interpreter import Interpreter, MeasureContext
from scoreocr.models import MeasureIR, PageGeometry, ScoreMeta, measure_total
from scoreocr.stages.crop import crop_paths, measure_crop_box
from scoreocr.workspace import Workspace


def _contexts_for_page(ws: Workspace, page: str, meta: ScoreMeta) -> dict[int, MeasureContext]:
    geo = PageGeometry.model_validate_json(ws.geometry_path(page).read_text())
    paths = crop_paths(ws, page)
    contexts = {}
    for si, system in enumerate(geo.systems):
        system_crop = Image.open(paths["systems"][si])
        # Force eager decode: this Image is shared across every MeasureContext in the
        # system and consumed concurrently by ThreadPoolExecutor workers, and PIL's
        # lazy first-decode is not thread-safe.
        system_crop.load()
        for mi, number in enumerate(system.measure_numbers):
            crop = Image.open(paths["measures"][number])
            # Force eager decode: consumed concurrently by ThreadPoolExecutor workers,
            # and PIL's lazy first-decode is not thread-safe.
            crop.load()
            x0, y0, _, _ = measure_crop_box(system, mi)
            line_ys = [
                y - y0 for staff in system.staves for y in staff.line_ys
            ]
            width = system.barline_xs[mi + 1] - system.barline_xs[mi]
            beat_xs = [
                (system.barline_xs[mi] - x0) + int(width * b / meta.time_beats)
                for b in range(meta.time_beats)
            ]
            # Phase 1 descope: previous-measure IR continuity (spec:
            # accidental/voice continuity input) is not populated under
            # concurrent interpretation; revisit in Phase 2.
            contexts[number] = MeasureContext(
                number=number, crop=crop, system_crop=system_crop, meta=meta,
                previous=None, staff_line_ys=line_ys, beat_xs=beat_xs,
            )
    return contexts


def _duration_feedback(ir: MeasureIR, meta: ScoreMeta) -> str | None:
    expected = measure_total(meta)
    problems = []
    for voice, events in ir.voices.items():
        total = sum(e.duration for e in events if not e.grace)
        if events and total != expected:
            problems.append(f"voice '{voice}' sums to {total}, expected {expected}")
    return "; ".join(problems) if problems else None


def _load_prior(ws: Workspace, number: int) -> MeasureIR | None:
    path = ws.measure_ir_path(number)
    if path.exists():
        return MeasureIR.model_validate_json(path.read_text())
    return None


def run_interpret(
    ws: Workspace,
    interpreter: Interpreter,
    *,
    only_measures: set[int] | None = None,
    feedback: dict[int, str] | None = None,
    max_workers: int = 4,
    on_progress=None,
) -> None:
    state = ws.load_state()
    feedback = feedback or {}

    if ws.score_meta_path.exists():
        meta = ScoreMeta.model_validate_json(ws.score_meta_path.read_text())
    else:
        first_page = state.pages[0].page
        meta, usage = interpreter.read_score_meta(Image.open(ws.source_path(first_page)))
        state.input_tokens += usage["input_tokens"]
        state.output_tokens += usage["output_tokens"]
        ws.score_meta_path.write_text(meta.model_dump_json(indent=2))

    contexts: dict[int, MeasureContext] = {}
    for entry in state.pages:
        contexts.update(_contexts_for_page(ws, entry.page, meta))
    targets = sorted(only_measures) if only_measures else sorted(contexts)
    total = len(targets)
    done = 0

    def work(number: int) -> tuple[int, MeasureIR | None, dict, str | None]:
        ctx = contexts[number]
        if number in feedback or only_measures:
            ctx.prior_attempt = _load_prior(ws, number)
            ctx.feedback = feedback.get(number)
        try:
            ir, usage = interpreter.interpret_measure(ctx)
            return number, ir, usage, None
        except Exception as exc:  # one bad measure never kills the job
            return number, None, {"input_tokens": 0, "output_tokens": 0}, str(exc)

    def run_batch(numbers, report: bool):
        nonlocal done
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for number, ir, usage, error in pool.map(work, numbers):
                state.input_tokens += usage["input_tokens"]
                state.output_tokens += usage["output_tokens"]
                if report and on_progress is not None:
                    done += 1
                    on_progress(min(done, total), total)
                if error is not None:
                    err_path = ws.measure_ir_path(number).with_suffix(".error.json")
                    err_path.write_text(json.dumps({"measure": number, "error": error}))
                    continue
                ws.measure_ir_path(number).write_text(ir.model_dump_json(indent=2))
                results.append((number, ir))
        return results

    results = run_batch(targets, report=True)

    # validation bounce-back: one retry per measure with the duration mismatch
    bounce = {}
    for number, ir in results:
        msg = _duration_feedback(ir, meta)
        if msg:
            bounce[number] = f"Duration check failed: {msg}. Re-examine rhythm, dots, and rests."
    if bounce:
        for number in bounce:
            contexts[number].prior_attempt = _load_prior(ws, number)
            contexts[number].feedback = bounce[number]
        feedback.update(bounce)
        run_batch(sorted(bounce), report=False)

    state.status = "interpreted"
    ws.save_state(state)
