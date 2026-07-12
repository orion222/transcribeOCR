from PIL import Image

from scoreocr.claude.tools import TOOL_DEFINITIONS, grid_overlay, image_to_content_block, zoom


def test_zoom_scales_and_clamps():
    img = Image.new("L", (200, 100), color=255)
    out = zoom(img, 50, 25, 150, 75, scale=4)
    assert out.size == (400, 200)
    out2 = zoom(img, -10, -10, 500, 500)  # clamped to full image
    assert out2.size == (800, 400)


def test_zoom_reversed_corners_does_not_raise():
    img = Image.new("L", (200, 100), color=255)
    out = zoom(img, 150, 50, 50, 150)  # x1<x0 and y1>y0 mixed reversal
    assert out.width > 0 and out.height > 0
    assert out.width <= 200 * 4 and out.height <= 100 * 4


def test_zoom_fully_outside_canvas_does_not_raise():
    img = Image.new("L", (200, 100), color=255)
    out = zoom(img, 300, 300, 400, 400)  # entirely beyond the bottom-right corner
    assert out.size == (4, 4)  # clamped to a 1x1 crop, scaled by 4


def test_zoom_zero_area_box_does_not_raise():
    img = Image.new("L", (200, 100), color=255)
    out = zoom(img, 100, 50, 100, 50)  # x0==x1 and y0==y1
    assert out.width > 0 and out.height > 0


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
