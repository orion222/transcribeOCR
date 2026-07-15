# src/scoreocr/web/merge.py
from pathlib import Path

from scoreocr.models import PageGeometry, ScoreMeta
from scoreocr.stages.assemble import load_measures
from scoreocr.stages.render import render_file
from scoreocr.stages.serialize import to_musicxml
from scoreocr.web.batch import BatchStore


def merge_batch(store: BatchStore, batch_id: str) -> Path:
    manifest = store.load(batch_id)
    done = [p for p in sorted(manifest.photos, key=lambda p: p.order)
            if p.status == "done"]
    if not done:
        raise ValueError("no successfully processed photos to merge")

    # (MeasureIR, is_system_start, is_page_start) across the whole batch
    records = []
    meta: ScoreMeta | None = None
    for ref in done:
        ws = store.workspace(batch_id, ref.job_id)
        if meta is None:
            meta = ScoreMeta.model_validate_json(ws.score_meta_path.read_text())
        for entry in ws.load_state().pages:
            geo = PageGeometry.model_validate_json(ws.geometry_path(entry.page).read_text())
            system_starts = {s.measure_numbers[0] for s in geo.systems[1:]}
            measures = load_measures(ws, entry.page)
            for j, measure in enumerate(measures):
                records.append((measure, measure.number in system_starts, j == 0))

    if not records:
        raise ValueError("no measure data found in processed photos")

    new_page, new_system = set(), set()
    merged = []
    for i, (measure, is_system, is_page) in enumerate(records, start=1):
        measure.number = i
        if is_page and i != 1:
            new_page.add(i)
        elif is_system:
            new_system.add(i)
        merged.append(measure)

    out_dir = store.merged_dir(batch_id)
    xml_path = out_dir / "score.musicxml"
    xml_path.write_bytes(to_musicxml(
        meta, merged,
        new_page_measures=frozenset(new_page),
        new_system_measures=frozenset(new_system),
    ))
    render_file(xml_path, out_dir / "preview", "score")
    return xml_path
