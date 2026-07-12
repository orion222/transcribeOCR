from lxml import etree as ET

from scoreocr.models import DIVISIONS, Direction, Event, MeasureIR, ScoreMeta, measure_total

# (voice, staff) per IR voice name
VOICE_CONFIG = {"treble": (1, 1), "bass": (2, 2)}
KNOWN_DYNAMICS = {"pp", "p", "mp", "mf", "f", "ff", "fff", "sfz", "fp"}

DOCTYPE = (
    '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 '
    'Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">'
)


def _attributes(meta: ScoreMeta) -> ET._Element:
    attrs = ET.Element("attributes")
    ET.SubElement(attrs, "divisions").text = str(DIVISIONS)
    key = ET.SubElement(attrs, "key")
    ET.SubElement(key, "fifths").text = str(meta.key_fifths)
    time = ET.SubElement(attrs, "time")
    ET.SubElement(time, "beats").text = str(meta.time_beats)
    ET.SubElement(time, "beat-type").text = str(meta.time_beat_type)
    # Note: keeping staves despite music21 behavior
    ET.SubElement(attrs, "staves").text = "2"
    for number, (sign, line) in (("1", ("G", "2")), ("2", ("F", "4"))):
        clef = ET.SubElement(attrs, "clef", number=number)
        ET.SubElement(clef, "sign").text = sign
        ET.SubElement(clef, "line").text = line
    return attrs


def _direction(d: Direction) -> ET._Element:
    if d.kind == "harmony":
        harmony = ET.Element("harmony")
        root = ET.SubElement(harmony, "root")
        ET.SubElement(root, "root-step").text = d.value[0].upper()
        kind = ET.SubElement(harmony, "kind")
        kind.text = "major"  # v1: chord symbol text preserved below
        kind.set("text", d.value)
        return harmony
    direction = ET.Element("direction")
    if d.staff == "treble":
        direction.set("placement", "above")
    dtype = ET.SubElement(direction, "direction-type")
    if d.kind == "dynamic" and d.value in KNOWN_DYNAMICS:
        dyn = ET.SubElement(dtype, "dynamics")
        ET.SubElement(dyn, d.value)
    else:
        ET.SubElement(dtype, "words").text = d.value
    if d.kind == "tempo" and "=" in d.value:
        try:
            bpm = float(d.value.split("=", 1)[1])
            ET.SubElement(direction, "sound", tempo=str(bpm))
        except ValueError:
            pass
    if d.staff:
        ET.SubElement(direction, "staff").text = str(VOICE_CONFIG[d.staff][1])
    return direction


def _event_notes(event: Event, voice: int, staff: int) -> list[ET._Element]:
    if event.kind == "rest":
        note = ET.Element("note")
        ET.SubElement(note, "rest")
        ET.SubElement(note, "duration").text = str(event.duration)
        ET.SubElement(note, "voice").text = str(voice)
        ET.SubElement(note, "type").text = event.note_type
        ET.SubElement(note, "staff").text = str(staff)
        return [note]

    notes = []
    for i, pitch in enumerate(event.pitches):
        note = ET.Element("note")
        # MusicXML child order: grace, chord, pitch, duration, tie, voice,
        # type, dot, time-modification, stem, staff, beam, notations
        if event.grace:
            grace = ET.SubElement(note, "grace")
            if event.slash:
                grace.set("slash", "yes")
        if i > 0:
            ET.SubElement(note, "chord")
        p = ET.SubElement(note, "pitch")
        ET.SubElement(p, "step").text = pitch.step
        if pitch.alter:
            ET.SubElement(p, "alter").text = str(pitch.alter)
        ET.SubElement(p, "octave").text = str(pitch.octave)
        if not event.grace:
            ET.SubElement(note, "duration").text = str(event.duration)
        if event.tie in ("start", "both"):
            ET.SubElement(note, "tie", type="start")
        if event.tie in ("stop", "both"):
            ET.SubElement(note, "tie", type="stop")
        ET.SubElement(note, "voice").text = str(voice)
        ET.SubElement(note, "type").text = event.note_type
        for _ in range(event.dots):
            ET.SubElement(note, "dot")
        if event.tuplet:
            tm = ET.SubElement(note, "time-modification")
            ET.SubElement(tm, "actual-notes").text = str(event.tuplet.actual)
            ET.SubElement(tm, "normal-notes").text = str(event.tuplet.normal)
        if event.stem:
            ET.SubElement(note, "stem").text = event.stem
        ET.SubElement(note, "staff").text = str(staff)
        if event.beam and i == 0:
            beam = ET.SubElement(note, "beam", number="1")
            beam.text = event.beam
        notations = ET.Element("notations")
        if event.tie in ("start", "both"):
            ET.SubElement(notations, "tied", type="start")
        if event.tie in ("stop", "both"):
            ET.SubElement(notations, "tied", type="stop")
        if event.tuplet and event.tuplet.position in ("start", "stop"):
            ET.SubElement(notations, "tuplet", type=event.tuplet.position)
        if len(notations):
            note.append(notations)
        notes.append(note)
    return notes


def _written_duration(events: list[Event]) -> int:
    # chord members share time; grace notes are untimed
    return sum(e.duration for e in events if not e.grace)


def to_musicxml(
    meta: ScoreMeta,
    measures: list[MeasureIR],
    *,
    new_page_measures: frozenset[int] = frozenset(),
    new_system_measures: frozenset[int] = frozenset(),
) -> bytes:
    root = ET.Element("score-partwise", version="4.0")
    if meta.title:
        work = ET.SubElement(root, "work")
        ET.SubElement(work, "work-title").text = meta.title
    part_list = ET.SubElement(root, "part-list")
    score_part = ET.SubElement(part_list, "score-part", id="P1")
    ET.SubElement(score_part, "part-name").text = "Piano"
    part = ET.SubElement(root, "part", id="P1")

    for idx, m in enumerate(measures):
        measure = ET.SubElement(part, "measure", number=str(m.number))
        if m.number in new_page_measures:
            ET.SubElement(measure, "print", **{"new-page": "yes"})
        elif m.number in new_system_measures:
            ET.SubElement(measure, "print", **{"new-system": "yes"})
        if idx == 0:
            measure.append(_attributes(meta))
        for d in m.directions:
            measure.append(_direction(d))
        treble = m.voices.get("treble", [])
        bass = m.voices.get("bass", [])
        for event in treble:
            measure.extend(_event_notes(event, *VOICE_CONFIG["treble"]))
        if treble and bass:
            backup = ET.SubElement(measure, "backup")
            ET.SubElement(backup, "duration").text = str(_written_duration(treble))
        for event in bass:
            measure.extend(_event_notes(event, *VOICE_CONFIG["bass"]))
        if idx == len(measures) - 1:
            barline = ET.SubElement(measure, "barline", location="right")
            ET.SubElement(barline, "bar-style").text = "light-heavy"

    return ET.tostring(
        root, xml_declaration=True, encoding="UTF-8",
        doctype=DOCTYPE, pretty_print=True,
    )
