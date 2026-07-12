from scoreocr.models import MeasureIR, PageGeometry, ScoreMeta
from scoreocr.stages.serialize import to_musicxml
from scoreocr.workspace import Workspace


def load_measures(ws: Workspace, page: str) -> list[MeasureIR]:
    return [
        MeasureIR.model_validate_json(p.read_text()) for p in ws.page_ir_paths(page)
    ]


def run_assemble(ws: Workspace) -> None:
    state = ws.load_state()
    meta = ScoreMeta.model_validate_json(ws.score_meta_path.read_text())

    all_measures: list[MeasureIR] = []
    new_page, new_system = set(), set()
    for entry in state.pages:
        geo = PageGeometry.model_validate_json(ws.geometry_path(entry.page).read_text())
        page_measures = load_measures(ws, entry.page)
        # standalone page file (its own first measure carries attributes)
        (ws.page_output_dir(entry.page) / "page.musicxml").write_bytes(
            to_musicxml(meta, page_measures)
        )
        new_page.add(geo.systems[0].measure_numbers[0])
        for system in geo.systems[1:]:
            new_system.add(system.measure_numbers[0])
        all_measures.extend(page_measures)

    first = all_measures[0].number
    new_page.discard(first)
    (ws.output_dir / "score.musicxml").write_bytes(
        to_musicxml(
            meta, all_measures,
            new_page_measures=frozenset(new_page),
            new_system_measures=frozenset(new_system),
        )
    )
    state.status = "assembled"
    ws.save_state(state)
