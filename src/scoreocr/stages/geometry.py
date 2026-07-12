from pathlib import Path

import cv2
import numpy as np

from scoreocr.models import PageGeometry, StaffBox, SystemBox
from scoreocr.workspace import Workspace

ROW_LINE_FRACTION = 0.4    # a staff line spans ≥40% of page width
BARLINE_FRACTION = 0.75    # a barline covers ≥75% of the system height


class GeometryConfidenceError(Exception):
    pass


def _run_centers(mask: np.ndarray) -> list[int]:
    """Centers of consecutive-True runs in a 1-D boolean mask."""
    centers, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        elif not v and start is not None:
            centers.append((start + i - 1) // 2)
            start = None
    if start is not None:
        centers.append((start + len(mask) - 1) // 2)
    return centers


def _group_staves(line_ys: list[int]) -> list[StaffBox]:
    if len(line_ys) < 5 or len(line_ys) % 5 != 0:
        raise GeometryConfidenceError(
            f"found {len(line_ys)} staff lines; expected a multiple of 5"
        )
    gaps = np.diff(line_ys)
    spacing = float(np.median(gaps))
    staves, current = [], [line_ys[0]]
    for y, gap in zip(line_ys[1:], gaps):
        if gap <= spacing * 2:
            current.append(y)
        else:
            staves.append(current)
            current = [y]
    staves.append(current)
    if any(len(s) != 5 for s in staves):
        raise GeometryConfidenceError(
            f"staff line groups of sizes {[len(s) for s in staves]}; expected 5s"
        )
    return [StaffBox(line_ys=s) for s in staves]


def detect_page_geometry(image_path: Path, page: str) -> PageGeometry:
    gray = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    dark = binary > 0
    height, width = dark.shape

    row_fraction = dark.sum(axis=1) / width
    line_ys = _run_centers(row_fraction > ROW_LINE_FRACTION)
    staves = _group_staves(line_ys)
    if len(staves) % 2 != 0:
        raise GeometryConfidenceError(f"{len(staves)} staves do not pair into grand staves")

    systems: list[SystemBox] = []
    next_measure = 1
    for i in range(0, len(staves), 2):
        treble, bass = staves[i], staves[i + 1]
        top, bottom = treble.top, bass.bottom
        band = dark[top : bottom + 1, :]
        col_fraction = band.sum(axis=0) / band.shape[0]
        if not (col_fraction > 0.05).any():
            raise GeometryConfidenceError("empty system band")
        left = int(np.argmax(col_fraction > 0.05))
        right = int(len(col_fraction) - np.argmax(col_fraction[::-1] > 0.05) - 1)
        barline_xs = _run_centers(col_fraction > BARLINE_FRACTION)
        if len(barline_xs) < 2:
            raise GeometryConfidenceError("no barlines found in system")
        n_measures = len(barline_xs) - 1
        systems.append(SystemBox(
            top=int(top), bottom=int(bottom), left=left, right=right,
            staves=[treble, bass], barline_xs=[int(x) for x in barline_xs],
            measure_numbers=list(range(next_measure, next_measure + n_measures)),
        ))
        next_measure += n_measures
    return PageGeometry(page=page, width=width, height=height, systems=systems)


def run_geometry(ws: Workspace) -> None:
    state = ws.load_state()
    next_measure = 1
    for entry in state.pages:
        geo = detect_page_geometry(ws.source_path(entry.page), entry.page)
        # shift measure numbers to continue across pages
        offset = next_measure - geo.systems[0].measure_numbers[0]
        for system in geo.systems:
            system.measure_numbers = [n + offset for n in system.measure_numbers]
        entry.measure_start = geo.systems[0].measure_numbers[0]
        entry.measure_end = geo.systems[-1].measure_numbers[-1]
        next_measure = entry.measure_end + 1
        ws.geometry_path(entry.page).write_text(geo.model_dump_json(indent=2))
    state.status = "geometry"
    ws.save_state(state)
