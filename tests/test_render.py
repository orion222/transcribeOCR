from scoreocr.models import Event, MeasureIR, Pitch, ScoreMeta
from scoreocr.stages.render import render_file
from scoreocr.stages.serialize import to_musicxml


def test_render_produces_svg(tmp_path):
    xml = to_musicxml(ScoreMeta(), [MeasureIR(
        number=1, confidence=1.0,
        voices={"treble": [Event(kind="note", duration=96, note_type="whole",
                                 pitches=[Pitch(step="C", octave=5)])],
                "bass": [Event(kind="rest", duration=96, note_type="whole")]},
    )])
    path = tmp_path / "score.musicxml"
    path.write_bytes(xml)
    outputs = render_file(path, tmp_path / "out", "preview")
    assert outputs and outputs[0].name == "preview-01.svg"
    assert "<svg" in outputs[0].read_text()
