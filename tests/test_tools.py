from PIL import Image

from scoreocr.claude.tools import TOOL_DEFINITIONS, grid_overlay, image_to_content_block, zoom


def test_zoom_scales_and_clamps():
    img = Image.new("L", (200, 100), color=255)
    out = zoom(img, 50, 25, 150, 75, scale=4)
    assert out.size == (400, 200)
    out2 = zoom(img, -10, -10, 500, 500)  # clamped to full image
    assert out2.size == (800, 400)


def test_grid_overlay_draws_lines():
    img = Image.new("L", (200, 100), color=255)
    out = grid_overlay(img, line_ys=[20, 40], beat_xs=[100])
    assert out.mode == "RGB"
    assert out.getpixel((0, 20)) == (255, 0, 0)
    assert out.getpixel((100, 0)) == (0, 0, 255)


def test_tool_definitions_shape():
    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert names == {"zoom", "grid_overlay"}
    zoom_def = next(t for t in TOOL_DEFINITIONS if t["name"] == "zoom")
    assert set(zoom_def["input_schema"]["required"]) == {"x0", "y0", "x1", "y1"}


def test_image_block():
    block = image_to_content_block(Image.new("L", (10, 10)))
    assert block["type"] == "image"
    assert block["source"]["media_type"] == "image/png"
