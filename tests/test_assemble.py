import json

from lxml import etree

from scoreocr.models import Event, MeasureIR, PageEntry, PageGeometry, Pitch, ScoreMeta, StaffBox, SystemBox
from scoreocr.stages.assemble import run_assemble
from scoreocr.workspace import Workspace


def _measure(number):
    return MeasureIR(
        number=number, confidence=0.9,
        voices={
            "treble": [Event(kind="note", duration=96, note_type="whole",
                             pitches=[Pitch(step="C", octave=5)])],
            "bass": [Event(kind="rest", duration=96, note_type="whole")],
        },
    )


def _geometry(page, numbers_by_system):
    staff = StaffBox(line_ys=[100, 112, 124, 136, 148])
    systems = [
        SystemBox(top=100, bottom=300, left=50, right=1000,
                  staves=[staff, staff],
                  barline_xs=[50] + [50 + 100 * (i + 1) for i in range(len(nums))],
                  measure_numbers=nums)
        for nums in numbers_by_system
    ]
    return PageGeometry(page=page, width=1200, height=800, systems=systems)


def _build_two_page_ws(tmp_path):
    ws = Workspace.create(tmp_path / "jobs")
    state = ws.load_state()
    state.pages = [
        PageEntry(page="p01", source_name="a.png", measure_start=1, measure_end=4),
        PageEntry(page="p02", source_name="b.png", measure_start=5, measure_end=8),
    ]
    ws.save_state(state)
    ws.score_meta_path.write_text(ScoreMeta().model_dump_json())
    ws.geometry_path("p01").write_text(_geometry("p01", [[1, 2], [3, 4]]).model_dump_json())
    ws.geometry_path("p02").write_text(_geometry("p02", [[5, 6], [7, 8]]).model_dump_json())
    for n in range(1, 9):
        ws.measure_ir_path(n).write_text(_measure(n).model_dump_json())
    return ws


def test_assemble_outputs(tmp_path):
    ws = _build_two_page_ws(tmp_path)
    run_assemble(ws)
    score = etree.parse(str(ws.output_dir / "score.musicxml"))
    assert len(score.findall(".//measure")) == 8
    # page seam: measure 5 starts a new page
    m5 = score.find(".//measure[@number='5']")
    assert m5.find("print").get("new-page") == "yes"
    # non-first system starts: measure 3 and 7
    m3 = score.find(".//measure[@number='3']")
    assert m3.find("print").get("new-system") == "yes"
    # attributes only on the first measure of the assembled score
    assert len(score.findall(".//measure/attributes")) == 1


def test_page_files_standalone(tmp_path):
    ws = _build_two_page_ws(tmp_path)
    run_assemble(ws)
    p2 = etree.parse(str(ws.page_output_dir("p02") / "page.musicxml"))
    measures = p2.findall(".//measure")
    assert [m.get("number") for m in measures] == ["5", "6", "7", "8"]
    # standalone page re-states attributes on ITS first measure
    assert measures[0].find("attributes") is not None
