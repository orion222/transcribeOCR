import pytest
from PIL import Image, ImageDraw

# Synthetic grand-staff page: 2 systems, 4 measures each.
STAFF_SPACING = 12          # px between staff lines
LEFT, RIGHT = 100, 1100
SYSTEM_TOPS = [200, 500]    # y of top line of the treble staff, per system
STAFF_GAP = 120             # treble top line -> bass top line offset
N_MEASURES = 4


def draw_page(width=1200, height=800, inter_staff_brackets=False,
              stacked_stems=False):
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
        if inter_staff_brackets:
            # Tuplet/pedal brackets in the gap between the treble and bass
            # staves: one short segment per measure, all at the same y. No
            # single one is staff-line-long, but together they cover half the
            # page width on that row.
            y = sys_top + 4 * STAFF_SPACING + (STAFF_GAP - 4 * STAFF_SPACING) // 2
            span = (RIGHT - LEFT) // N_MEASURES
            for k in range(N_MEASURES):
                x0 = LEFT + k * span + span // 10
                d.line([(x0, y), (x0 + int(span * 0.75), y)], fill=0, width=2)
        if stacked_stems:
            # A treble stem and a bass stem sharing an x, mid-measure. Together
            # with the staff lines they ink more than BARLINE_FRACTION of the
            # system band, but the inter-staff gap breaks the run.
            x = LEFT + (RIGHT - LEFT) // (2 * N_MEASURES)
            d.line([(x, sys_top), (x, sys_top + 70)], fill=0, width=3)
            d.line([(x, sys_top + 100), (x, bottom)], fill=0, width=3)
    return img


@pytest.fixture
def synthetic_page(tmp_path):
    path = tmp_path / "page.png"
    draw_page().save(path)
    return path


@pytest.fixture
def synthetic_page_with_brackets(tmp_path):
    path = tmp_path / "page_brackets.png"
    draw_page(inter_staff_brackets=True).save(path)
    return path


@pytest.fixture
def synthetic_page_with_stems(tmp_path):
    path = tmp_path / "page_stems.png"
    draw_page(stacked_stems=True).save(path)
    return path
