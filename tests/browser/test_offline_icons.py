"""With the network off, both pages make no request outside 127.0.0.1 and
every icon still draws, including the icon-only buttons."""

import pytest

from tests.conftest import make_test_image

# Each icon's ::before glyph and whether the solid font is loaded.
ICON_STATE = """async () => {
  await document.fonts.ready;
  const icons = [...document.querySelectorAll('i.fas')].filter(i => i.getClientRects().length);
  return {
    font: document.fonts.check('900 16px "Font Awesome 6 Free"'),
    blank: icons.filter(i => {
      const c = getComputedStyle(i, '::before').content;
      return !c || c === 'none' || c === 'normal' || i.getBoundingClientRect().width < 4;
    }).map(i => i.className),
    count: icons.length,
  };
}"""


@pytest.fixture()
def offline(browser, live_url):
    """A tab that records and blocks every request that is not to the local server."""
    context = browser.new_context(base_url=live_url)
    outside = []

    def route(r):
        if r.request.url.startswith(live_url):
            r.continue_()
        else:
            outside.append(r.request.url)
            r.abort()

    context.route("**/*", route)
    tab = context.new_page()
    yield tab, outside
    context.close()


def test_the_template_designer_stays_local_and_keeps_its_icons(offline):
    tab, outside = offline
    tab.goto("/template")
    tab.wait_for_selector("#previewImage:not([hidden])")
    tab.click("[data-add='text']")
    tab.click("[data-add='text']")
    state = tab.evaluate(ICON_STATE)
    assert outside == []
    assert state["font"] and state["count"] > 10
    assert state["blank"] == []
    # The icon-only layer move buttons draw a glyph of real width.
    down = tab.locator("#layerList button[aria-label^='Move layer'][aria-label$='down'] i").first
    assert down.bounding_box()["width"] >= 8


def test_the_photo_editor_stays_local_and_keeps_its_icons(offline, tmp_path):
    tab, outside = offline
    photo = tmp_path / "photo.png"
    photo.write_bytes(make_test_image(120, 80, (40, 120, 200)).getvalue())
    tab.goto("/")
    tab.set_input_files("#fileInput", str(photo))
    tab.wait_for_selector("#preview-image[src^='/api/original/']")
    tab.click("[data-section='textSection']")
    tab.click("[data-action='add-text']")
    state = tab.evaluate(ICON_STATE)
    assert outside == []
    assert state["font"] and state["count"] > 5
    assert state["blank"] == []
    # The icon-only Left, Center and Right align buttons draw a glyph.
    for align in ("left", "center", "right"):
        assert tab.locator(f".align-btn[data-align='{align}'] i").first.bounding_box()["width"] >= 8
