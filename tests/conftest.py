import pytest
from PIL import Image, ImageDraw

# Synthetic grand-staff page: 2 systems, 4 measures each.
STAFF_SPACING = 12          # px between staff lines
LEFT, RIGHT = 100, 1100
SYSTEM_TOPS = [200, 500]    # y of top line of the treble staff, per system
STAFF_GAP = 120             # treble top line -> bass top line offset
N_MEASURES = 4


def draw_page(width=1200, height=800):
    img = Image.new("L", (width, height), color=255)
    d = ImageDraw.Draw(img)
    for sys_top in SYSTEM_TOPS:
        for staff_top in (sys_top, sys_top + STAFF_GAP):
            for i in range(5):
                y = staff_top + i * STAFF_SPACING
                d.line([(LEFT, y), (RIGHT, y)], fill=0, width=2)
        bottom = sys_top + STAFF_GAP + 4 * STAFF_SPACING
        for k in range(N_MEASURES + 1):
            x = LEFT + k * (RIGHT - LEFT) // N_MEASURES
            d.line([(x, sys_top), (x, bottom)], fill=0, width=3)
    return img


@pytest.fixture
def synthetic_page(tmp_path):
    path = tmp_path / "page.png"
    draw_page().save(path)
    return path
