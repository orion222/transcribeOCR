from pathlib import Path

import verovio

from scoreocr.workspace import Workspace


def render_file(xml_path: Path, out_dir: Path, stem: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    tk = verovio.toolkit()
    tk.setOptions({"svgViewBox": True, "adjustPageHeight": True})
    if not tk.loadData(xml_path.read_text()):
        raise RuntimeError(f"verovio failed to load {xml_path}")
    outputs = []
    for page in range(1, tk.getPageCount() + 1):
        svg_path = out_dir / f"{stem}-{page:02d}.svg"
        svg_path.write_text(tk.renderToSVG(page))
        outputs.append(svg_path)
    return outputs


def run_render(ws: Workspace) -> None:
    state = ws.load_state()
    render_file(ws.output_dir / "score.musicxml", ws.output_dir / "preview", "score")
    for entry in state.pages:
        page_xml = ws.page_output_dir(entry.page) / "page.musicxml"
        render_file(page_xml, ws.page_output_dir(entry.page), "preview")
    state.status = "rendered"
    ws.save_state(state)
