from types import SimpleNamespace

from scoreocr.claude.interpreter import Interpreter
from scoreocr.models import Event, MeasureIR, Pitch, ScoreMeta
from scoreocr.stages.selfcheck import Discrepancy, DiscrepancyReport, run_selfcheck
from scoreocr.stages.assemble import run_assemble
from scoreocr.stages.crop import run_crop
from scoreocr.stages.geometry import run_geometry
from scoreocr.stages.ingest import run_ingest
from scoreocr.stages.interpret import run_interpret
from scoreocr.stages.render import run_render
from scoreocr.workspace import Workspace


def _good_ir(number):
    return MeasureIR(number=number, confidence=0.9, voices={
        "treble": [Event(kind="note", duration=96, note_type="whole",
                         pitches=[Pitch(step="C", octave=5)])],
        "bass": [Event(kind="rest", duration=96, note_type="whole")]})


class StubInterpreter(Interpreter):
    def __init__(self, reports):
        super().__init__(client=None)
        self.reports = list(reports)      # one DiscrepancyReport per compare call
        self.reinterpreted = []

    def read_score_meta(self, page_image):
        return ScoreMeta(), {"input_tokens": 0, "output_tokens": 0}

    def interpret_measure(self, ctx):
        self.reinterpreted.append(ctx.number)
        return _good_ir(ctx.number), {"input_tokens": 0, "output_tokens": 0}

    def compare_images(self, source, rendered, measure_numbers):
        return self.reports.pop(0), {"input_tokens": 0, "output_tokens": 0}


def _pipeline_ws(tmp_path, synthetic_page, stub):
    ws = Workspace.create(tmp_path / "jobs")
    run_ingest(ws, [synthetic_page])
    run_geometry(ws)
    run_crop(ws)
    run_interpret(ws, stub)
    run_assemble(ws)
    run_render(ws)
    return ws


def test_clean_selfcheck_terminates(tmp_path, synthetic_page):
    clean = DiscrepancyReport(discrepancies=[])
    stub = StubInterpreter(reports=[clean, clean, clean, clean])  # 4 systems
    ws = _pipeline_ws(tmp_path, synthetic_page, stub)
    remaining = run_selfcheck(ws, stub)
    assert remaining == [] and stub.reinterpreted == []


def test_discrepancy_triggers_rerun_then_resolves(tmp_path, synthetic_page):
    bad = DiscrepancyReport(discrepancies=[
        Discrepancy(measure=2, staff="treble", description="rendered E, source shows Eb")])
    clean = DiscrepancyReport(discrepancies=[])
    # round 1: system 1 dirty, others clean; round 2: all clean
    stub = StubInterpreter(reports=[bad, clean, clean, clean, clean, clean, clean, clean])
    ws = _pipeline_ws(tmp_path, synthetic_page, stub)
    remaining = run_selfcheck(ws, stub, max_rounds=2)
    assert remaining == []
    assert 2 in stub.reinterpreted
