import pytest
from PIL import Image

from scoreocr.stages.geometry import (
    GeometryConfidenceError, detect_page_geometry,
)


def test_detects_two_systems_four_measures(synthetic_page):
    geo = detect_page_geometry(synthetic_page, "p01")
    assert len(geo.systems) == 2
    for system in geo.systems:
        assert len(system.staves) == 2
        assert all(len(s.line_ys) == 5 for s in system.staves)
        assert len(system.barline_xs) == 5   # 4 measures
        assert len(system.measure_numbers) == 4


def test_measure_numbers_continue_across_systems(synthetic_page):
    geo = detect_page_geometry(synthetic_page, "p01")
    assert geo.systems[0].measure_numbers == [1, 2, 3, 4]
    assert geo.systems[1].measure_numbers == [5, 6, 7, 8]


def test_inter_staff_brackets_are_not_staff_lines(synthetic_page_with_brackets):
    """Short collinear marks must not sum into a phantom staff line.

    Engraved scores put tuplet/pedal brackets in the gap between the staves of a
    grand staff, one per measure and all on the same row. Scoring a row by total
    dark pixels counts them as a single line spanning half the page, which
    yields a staff-line count that is not a multiple of 5.
    """
    geo = detect_page_geometry(synthetic_page_with_brackets, "p01")
    assert len(geo.systems) == 2
    for system in geo.systems:
        assert [len(s.line_ys) for s in system.staves] == [5, 5]


def test_stacked_stems_are_not_barlines(synthetic_page_with_stems):
    """Vertically stacked collinear marks must not sum into a phantom barline.

    A treble stem above a bass stem at the same x inks more of the system band
    than a barline threshold allows for, without ever forming a barline's
    continuous run. Counting it splits one measure into two, which silently
    shifts every measure number after it.
    """
    geo = detect_page_geometry(synthetic_page_with_stems, "p01")
    for system in geo.systems:
        assert len(system.barline_xs) == 5   # 4 measures
        assert len(system.measure_numbers) == 4
    assert geo.systems[1].measure_numbers == [5, 6, 7, 8]


def test_blank_page_raises(tmp_path):
    blank = tmp_path / "blank.png"
    Image.new("L", (1200, 800), color=255).save(blank)
    with pytest.raises(GeometryConfidenceError):
        detect_page_geometry(blank, "p01")
