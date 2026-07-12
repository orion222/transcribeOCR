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


def test_blank_page_raises(tmp_path):
    blank = tmp_path / "blank.png"
    Image.new("L", (1200, 800), color=255).save(blank)
    with pytest.raises(GeometryConfidenceError):
        detect_page_geometry(blank, "p01")
