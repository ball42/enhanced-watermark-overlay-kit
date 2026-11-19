"""Template designer at 320 px (a phone, or 1280 px at 400% zoom): nothing
runs off the right edge, and the More menu opens inside the screen."""

import pytest

OFF_SCREEN = """() => [...document.querySelectorAll('body *')].filter((e) => {
  const r = e.getBoundingClientRect();
  return r.width && (r.right > innerWidth + 0.5 || r.left < -0.5);
}).map((e) => `${e.id || e.className || e.tagName} ${Math.round(e.getBoundingClientRect().right)}`)"""


@pytest.mark.parametrize("dark", [False, True])
def test_nothing_passes_the_right_edge_at_320(page, dark):
    page.set_viewport_size({"width": 320, "height": 900})
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    if dark:
        page.click(".ewok-theme-toggle")
    assert page.evaluate("document.documentElement.scrollWidth") == 320
    assert page.evaluate(OFF_SCREEN) == []
    for sel in (".ewok-theme-toggle", "#downloadPackage", "#preflightToggle"):
        box = page.locator(sel).bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= 320, sel

    page.click("#moreActions > summary")
    assert page.evaluate(OFF_SCREEN) == []
    page.click("#moreActions > summary")
    page.click("#preflightToggle")
    assert page.evaluate(OFF_SCREEN) == []
