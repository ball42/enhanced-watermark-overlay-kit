"""Photo editor at 320 px (a phone, or 1280 px at 400% zoom): with a photo
and one text and one image overlay, nothing runs off the right edge and no
control is cut off inside its row."""

import pytest

from .test_photo_live import upload
from .test_template_narrow import OFF_SCREEN

# A control that ends past the right edge of the box it sits in is cut off
# (the text overlay's Delete read "Dele"). A rotated chevron's box pokes out
# a pixel without moving anything, so transformed elements are left out.
PAST_ITS_BOX = """() => [...document.querySelectorAll('.controls-panel *')].filter((e) => {
  const r = e.getBoundingClientRect();
  if (getComputedStyle(e).transform !== 'none') return false;
  return r.width && r.right > e.parentElement.getBoundingClientRect().right + 0.5;
}).map((e) => `${e.className || e.tagName} ${Math.round(e.getBoundingClientRect().right)}`)"""


@pytest.mark.parametrize("dark", [False, True])
def test_nothing_passes_the_right_edge_at_320(page, tmp_path, dark):
    page.set_viewport_size({"width": 320, "height": 900})
    upload(page, tmp_path)
    if dark:
        page.click(".ewok-theme-toggle")
    page.click('[data-section="textSection"]')
    page.click('[data-action="add-text"]')
    page.click('[data-section="imageOverlaySection"]')
    page.click('[data-action="add-image-overlay"]')
    page.evaluate("window.scrollTo(0, 0)")
    assert page.evaluate(
        "document.documentElement.scrollWidth === document.documentElement.clientWidth")
    assert page.evaluate(OFF_SCREEN) == []
    assert page.evaluate(PAST_ITS_BOX) == []
    for sel in ('.text-overlay-header [data-action="remove-overlay"]',
                '.image-overlay-header [data-action="remove-image-overlay"]'):
        box = page.locator(sel).bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= 320, sel
