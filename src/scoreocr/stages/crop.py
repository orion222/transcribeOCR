from pathlib import Path

from PIL import Image

from scoreocr.models import PageGeometry, SystemBox
from scoreocr.workspace import Workspace

VERTICAL_MARGIN = 30  # px above/below system for ledger lines
HORIZONTAL_PAD = 8


def measure_crop_box(system: SystemBox, index: int, margin: int = VERTICAL_MARGIN):
    x0 = max(system.barline_xs[index] - HORIZONTAL_PAD, 0)
    x1 = system.barline_xs[index + 1] + HORIZONTAL_PAD
    y0 = max(system.top - margin, 0)
    y1 = system.bottom + margin
    return (x0, y0, x1, y1)


def run_crop(ws: Workspace) -> None:
    state = ws.load_state()
    for entry in state.pages:
        geo = PageGeometry.model_validate_json(ws.geometry_path(entry.page).read_text())
        img = Image.open(ws.source_path(entry.page))
        crops = ws.crops_dir(entry.page)
        (crops / "systems").mkdir(exist_ok=True)
        (crops / "measures").mkdir(exist_ok=True)
        for si, system in enumerate(geo.systems, start=1):
            box = (system.left, max(system.top - VERTICAL_MARGIN, 0),
                   system.right, system.bottom + VERTICAL_MARGIN)
            img.crop(box).save(crops / "systems" / f"s{si:02d}.png")
            for mi, number in enumerate(system.measure_numbers):
                img.crop(measure_crop_box(system, mi)).save(
                    crops / "measures" / f"m{number:03d}.png"
                )
    state.status = "cropped"
    ws.save_state(state)


def crop_paths(ws: Workspace, page: str) -> dict:
    crops = ws.crops_dir(page)
    measures = {
        int(p.stem[1:]): p for p in sorted((crops / "measures").glob("m*.png"))
    }
    return {"systems": sorted((crops / "systems").glob("s*.png")), "measures": measures}
