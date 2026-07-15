from scoreocr.pipeline import run_pipeline
from scoreocr.web.audio import musicxml_to_midi
from scoreocr.workspace import Workspace
from tests.test_cli import StubInterpreter


def test_musicxml_to_midi_produces_a_midi_header(tmp_path, synthetic_page):
    ws = Workspace.create(tmp_path / "jobs")
    run_pipeline(ws, StubInterpreter(), [synthetic_page])
    xml = (ws.output_dir / "score.musicxml").read_text()
    data = musicxml_to_midi(xml)
    assert data[:4] == b"MThd"      # Standard MIDI File header chunk
    assert len(data) > 8


def test_musicxml_to_midi_rejects_garbage():
    try:
        musicxml_to_midi("not xml at all")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
