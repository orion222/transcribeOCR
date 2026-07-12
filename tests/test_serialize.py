from lxml import etree

import music21

from scoreocr.models import Direction, Event, MeasureIR, Pitch, ScoreMeta
from scoreocr.stages.serialize import to_musicxml


def _meta():
    return ScoreMeta(title="Test", key_fifths=-4, time_beats=4, time_beat_type=4)


def _simple_measure(number=1):
    return MeasureIR(
        number=number,
        confidence=0.9,
        voices={
            "treble": [
                Event(kind="note", duration=48, note_type="half",
                      pitches=[Pitch(step="E", alter=-1, octave=4)]),
                Event(kind="chord", duration=48, note_type="half",
                      pitches=[Pitch(step="A", alter=-1, octave=4),
                               Pitch(step="C", octave=5)]),
            ],
            "bass": [
                Event(kind="rest", duration=96, note_type="whole"),
            ],
        },
        directions=[Direction(kind="dynamic", value="mf", beat=1.0, staff="treble")],
    )


def _tree(measures, **kw):
    return etree.fromstring(to_musicxml(_meta(), measures, **kw))


def test_structure_and_attributes():
    root = _tree([_simple_measure()])
    assert root.tag == "score-partwise"
    m1 = root.find(".//measure[@number='1']")
    assert m1.findtext("attributes/divisions") == "24"
    assert m1.findtext("attributes/key/fifths") == "-4"
    assert m1.findtext("attributes/staves") == "2"


def test_backup_and_voices():
    m1 = _tree([_simple_measure()]).find(".//measure")
    assert m1.findtext("backup/duration") == "96"
    voices = {n.findtext("voice") for n in m1.findall("note")}
    assert voices == {"1", "2"}


def test_chord_marker():
    notes = _tree([_simple_measure()]).findall(".//note")
    chord_notes = [n for n in notes if n.find("chord") is not None]
    assert len(chord_notes) == 1  # 2nd pitch of the chord event only


def test_pitch_alter():
    note = _tree([_simple_measure()]).find(".//note")
    assert note.findtext("pitch/step") == "E"
    assert note.findtext("pitch/alter") == "-1"


def test_final_barline_and_print_marks():
    measures = [_simple_measure(1), _simple_measure(2)]
    root = _tree(measures, new_system_measures=frozenset({2}))
    m2 = root.find(".//measure[@number='2']")
    assert m2.find("print").get("new-system") == "yes"
    assert m2.findtext("barline/bar-style") == "light-heavy"


def test_grace_note_has_no_duration():
    m = _simple_measure()
    m.voices["treble"].insert(0, Event(
        kind="note", duration=0, note_type="eighth", grace=True, slash=True,
        pitches=[Pitch(step="D", octave=5)]))
    note = _tree([m]).find(".//note")
    assert note.find("grace") is not None and note.find("duration") is None


def test_music21_roundtrip():
    xml = to_musicxml(_meta(), [_simple_measure()])
    score = music21.converter.parseData(xml.decode())
    # music21 10.5 imports a <staves>2</staves> part as 2 PartStaff objects
    # (grouped by a StaffGroup) rather than a single Part with 2 staves.
    parts = list(score.parts)
    assert len(parts) == 2
    assert all(isinstance(p, music21.stream.PartStaff) for p in parts)
    staff_groups = list(score.recurse().getElementsByClass(music21.layout.StaffGroup))
    assert len(staff_groups) == 1
    assert list(staff_groups[0].getSpannedElements()) == parts
