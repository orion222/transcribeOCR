from scoreocr.models import Event, MeasureIR, Pitch, ScoreMeta
from scoreocr.stages.serialize import to_musicxml
from scoreocr.stages.validate import validate_musicxml


def _measure(number, treble_duration=96):
    return MeasureIR(
        number=number, confidence=0.9,
        voices={
            "treble": [Event(kind="note", duration=treble_duration, note_type="whole",
                             pitches=[Pitch(step="C", octave=5)])],
            "bass": [Event(kind="rest", duration=96, note_type="whole")],
        },
    )


META = ScoreMeta()  # 4/4 → 96 divisions per measure


def test_valid_score_has_no_issues():
    xml = to_musicxml(META, [_measure(1), _measure(2)])
    assert validate_musicxml(xml, META, [1, 2]) == []


def test_duration_mismatch_flagged():
    xml = to_musicxml(META, [_measure(1, treble_duration=90)])
    issues = validate_musicxml(xml, META, [1])
    assert any(i.code == "duration" and i.measure == 1 for i in issues)


def test_missing_measure_flagged():
    xml = to_musicxml(META, [_measure(1), _measure(3)])
    issues = validate_musicxml(xml, META, [1, 2, 3])
    assert any(i.code == "numbering" for i in issues)


def test_broken_xml_flagged():
    issues = validate_musicxml(b"<score-partwise><oops>", META, [1])
    assert issues[0].code == "xml"
