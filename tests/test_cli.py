import scoreocr.cli as cli
from scoreocr.claude.interpreter import Interpreter
from scoreocr.models import Event, MeasureIR, Pitch, ScoreMeta


class StubInterpreter(Interpreter):
    def __init__(self):
        super().__init__(client=None)

    def read_score_meta(self, page_image):
        return ScoreMeta(), {"input_tokens": 0, "output_tokens": 0}

    def interpret_measure(self, ctx):
        ir = MeasureIR(number=ctx.number, confidence=0.9, voices={
            "treble": [Event(kind="note", duration=96, note_type="whole",
                             pitches=[Pitch(step="C", octave=5)])],
            "bass": [Event(kind="rest", duration=96, note_type="whole")]})
        return ir, {"input_tokens": 0, "output_tokens": 0}


def test_end_to_end(tmp_path, synthetic_page, monkeypatch, capsys):
    monkeypatch.setattr(cli, "build_interpreter", lambda: StubInterpreter())
    code = cli.main([
        "run", str(synthetic_page), "--jobs-root", str(tmp_path / "jobs"),
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "score.musicxml" in out
    jobs = list((tmp_path / "jobs").iterdir())
    assert len(jobs) == 1
    score = jobs[0] / "output" / "score.musicxml"
    assert score.exists()
    previews = list((jobs[0] / "output" / "preview").glob("*.svg"))
    assert previews
