from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from scoreocr.models import PageEntry
from scoreocr.workspace import Workspace

RASTER_DPI = 300


def _iter_page_images(path: Path):
    """Yield (source_name, PIL.Image) for one input file."""
    if path.suffix.lower() == ".pdf":
        doc = pdfium.PdfDocument(str(path))
        for i, page in enumerate(doc):
            bitmap = page.render(scale=RASTER_DPI / 72)
            yield f"{path.name}#page{i + 1}", bitmap.to_pil()
    else:
        yield path.name, Image.open(path)


def run_ingest(ws: Workspace, inputs: list[Path]) -> None:
    state = ws.load_state()
    state.pages = []
    n = 0
    for input_path in inputs:
        for source_name, img in _iter_page_images(Path(input_path)):
            n += 1
            page = f"p{n:02d}"
            img.convert("L").save(ws.source_path(page))
            state.pages.append(PageEntry(page=page, source_name=source_name))
    state.status = "ingested"
    ws.save_state(state)
