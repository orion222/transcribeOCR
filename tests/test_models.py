import pytest
from pydantic import ValidationError
from scoreocr.models import (
    DIVISIONS, Event, MeasureIR, Pitch, ScoreMeta, measure_total,
)


def test_divisions_constant():
    assert DIVISIONS == 24


def test_pitch_rejects_bad_step():
    with pytest.raises(ValidationError):
        Pitch(step="H", octave=4)


def test_measure_ir_confidence_bounds():
    with pytest.raises(ValidationError):
        MeasureIR(number=1, voices={}, confidence=1.5)


def test_measure_total_4_4():
    meta = ScoreMeta(time_beats=4, time_beat_type=4)
    assert measure_total(meta) == 96  # 4 quarters * 24


def test_measure_total_6_8():
    meta = ScoreMeta(time_beats=6, time_beat_type=8)
    assert measure_total(meta) == 72  # 6 eighths * 12


def test_event_defaults():
    e = Event(kind="rest", duration=24, note_type="quarter")
    assert e.pitches == [] and e.dots == 0 and e.tie is None
