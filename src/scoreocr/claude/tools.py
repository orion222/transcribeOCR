import base64
import io

from PIL import Image, ImageDraw


def zoom(img: Image.Image, x0: int, y0: int, x1: int, y1: int, scale: int = 4) -> Image.Image:
    # Order the coordinates so x0<=x1 and y0<=y1 (LLM-generated boxes may be reversed).
    x0, x1 = min(x0, x1), max(x0, x1)
    y0, y1 = min(y0, y1), max(y0, y1)
    # Clamp into image bounds while guaranteeing a non-empty (>=1x1) crop box, even
    # for degenerate or fully-out-of-range input.
    x0 = max(0, min(x0, img.width - 1))
    x1 = max(x0 + 1, min(x1, img.width))
    y0 = max(0, min(y0, img.height - 1))
    y1 = max(y0 + 1, min(y1, img.height))
    region = img.crop((x0, y0, x1, y1))
    return region.resize((region.width * scale, region.height * scale), Image.LANCZOS)


def grid_overlay(img: Image.Image, line_ys: list[int], beat_xs: list[int]) -> Image.Image:
    out = img.convert("RGB")
    draw = ImageDraw.Draw(out)
    for y in line_ys:
        draw.line([(0, y), (out.width, y)], fill=(255, 0, 0), width=1)
    for x in beat_xs:
        draw.line([(x, 0), (x, out.height)], fill=(0, 0, 255), width=1)
    return out


TOOL_DEFINITIONS = [
    {
        "name": "zoom",
        "description": (
            "Enlarge a region of the measure crop 4x for closer inspection. "
            "Coordinates are pixels in the measure crop you were shown. Use this "
            "when an accidental, dot, ledger line, or notehead position is ambiguous."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "x0": {"type": "integer"}, "y0": {"type": "integer"},
                "x1": {"type": "integer"}, "y1": {"type": "integer"},
            },
            "required": ["x0", "y0", "x1", "y1"],
        },
    },
    {
        "name": "grid_overlay",
        "description": (
            "Return the measure crop with red horizontal guides on every staff line "
            "and blue vertical beat guides. Use this to resolve exact notehead "
            "positions relative to staff lines and spaces."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


def image_to_content_block(img: Image.Image) -> dict:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.standard_b64encode(buf.getvalue()).decode(),
        },
    }
