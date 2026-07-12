from scoreocr.claude.interpreter import Interpreter
from scoreocr.models import Event, MeasureIR, Pitch, ScoreMeta
from scoreocr.stages.assemble import run_assemble
from scoreocr.stages.crop import run_crop
from scoreocr.stages.geometry import run_geometry
from scoreocr.stages.ingest import run_ingest
from scoreocr.stages.interpret import run_interpret
from scoreocr.stages.validate import validate_musicxml
from scoreocr.workspace import Workspace


def _good_ir(number):
    return MeasureIR(number=number, confidence=0.9, voices={
        "treble": [Event(kind="note", duration=96, note_type="whole",
                         pitches=[Pitch(step="C", octave=5)])],
        "bass": [Event(kind="rest", duration=96, note_type="whole")]})


def _bad_ir(number):  # duration short by an eighth
    ir = _good_ir(number)
    ir.voices["treble"][0].duration = 84
    return ir


class StubInterpreter(Interpreter):
    """Bypasses the API: returns scripted IRs, records feedback it was given."""

    def __init__(self, ir_factory):
        super().__init__(client=None)
        self.ir_factory = ir_factory
        self.feedback_seen = {}

    def read_score_meta(self, page_image):
        return ScoreMeta(), {"input_tokens": 10, "output_tokens": 5}

    def interpret_measure(self, ctx):
        if ctx.feedback:
            self.feedback_seen[ctx.number] = ctx.feedback
        return self.ir_factory(ctx), {"input_tokens": 100, "output_tokens": 50}


def _ws(tmp_path, synthetic_page):
    ws = Workspace.create(tmp_path / "jobs")
    run_ingest(ws, [synthetic_page])
    run_geometry(ws)
    run_crop(ws)
    return ws


def test_interpret_writes_all_measures(tmp_path, synthetic_page):
    ws = _ws(tmp_path, synthetic_page)
    stub = StubInterpreter(lambda ctx: _good_ir(ctx.number))
    run_interpret(ws, stub)
    state = ws.load_state()
    assert state.status == "interpreted"
    assert state.input_tokens > 0
    for n in range(1, 9):
        assert ws.measure_ir_path(n).exists()
    assert ws.score_meta_path.exists()


def test_duration_bounceback_reruns_with_feedback(tmp_path, synthetic_page):
    ws = _ws(tmp_path, synthetic_page)

    def factory(ctx):
        if ctx.number == 3 and ctx.feedback is None:
            return _bad_ir(3)  # first attempt wrong
        return _good_ir(ctx.number)

    stub = StubInterpreter(factory)
    run_interpret(ws, stub)
    assert 3 in stub.feedback_seen
    assert "84" in stub.feedback_seen[3]  # mismatch reported in feedback


def test_only_measures_rerun(tmp_path, synthetic_page):
    ws = _ws(tmp_path, synthetic_page)
    stub = StubInterpreter(lambda ctx: _good_ir(ctx.number))
    run_interpret(ws, stub)
    stub2 = StubInterpreter(lambda ctx: _good_ir(ctx.number))
    run_interpret(ws, stub2, only_measures={5},
                  feedback={5: "beat 3 should be an Eb"})
    assert stub2.feedback_seen == {5: "beat 3 should be an Eb"}


def test_measure_failure_writes_error_and_job_continues(tmp_path, synthetic_page):
    ws = _ws(tmp_path, synthetic_page)

    def factory(ctx):
        if ctx.number == 3:
            raise RuntimeError("simulated interpreter failure")
        return _good_ir(ctx.number)

    stub = StubInterpreter(factory)
    run_interpret(ws, stub)

    state = ws.load_state()
    assert state.status == "interpreted"  # the job did not die on one bad measure

    err_path = ws.measure_ir_path(3).with_suffix(".error.json")
    assert err_path.exists()
    assert not ws.measure_ir_path(3).exists()
    for n in [1, 2, 4, 5, 6, 7, 8]:
        assert ws.measure_ir_path(n).exists()

    # assemble must not choke on the missing measure (nor on the error sidecar
    # file, which used to collide with the "m*.json" IR glob)
    run_assemble(ws)
    assert ws.load_state().status == "assembled"

    meta = ScoreMeta.model_validate_json(ws.score_meta_path.read_text())
    issues = validate_musicxml(
        (ws.output_dir / "score.musicxml").read_bytes(), meta, list(range(1, 9)),
    )
    codes = {issue.code for issue in issues}
    assert "measure-count" in codes or "numbering" in codes
