"""Photo editor: every watermark and overlay control has a name a screen
reader can say, and each overlay row's names carry its number."""

from importlib import resources

from .test_photo_live import upload

AXE = resources.files("axe_playwright_python").joinpath("axe.min.js").read_text()
RULES = ["label", "select-name", "aria-allowed-role"]
SECTIONS = ("wallpaperSection", "textSection", "imageOverlaySection", "backgroundSection", "watermarkSection")


def name_of(page, selector):
    return page.evaluate(
        """s => { const el = document.querySelector(s);
                  return el.getAttribute('aria-label') || (el.labels[0] || {}).textContent; }""", selector)


def axe(page):
    page.add_script_tag(content=AXE)
    found = page.evaluate(
        "async (rules) => (await axe.run(document, {runOnly: rules})).violations"
        ".map(v => v.id + ': ' + v.nodes.map(n => n.target.join(' ')).join(', '))", RULES)
    return found


def test_watermark_and_overlay_controls_have_names(page, tmp_path):
    upload(page, tmp_path)
    for section in SECTIONS:
        page.click(f'[data-section="{section}"]')
    page.click('[data-action="add-text"]')
    page.click('[data-action="add-text"]')
    page.click('[data-action="add-image-overlay"]')

    assert axe(page) == []

    assert name_of(page, "#watermarkPosition") == "Position"
    assert name_of(page, "#watermarkOpacity") == "Opacity"
    rows = page.locator(".text-overlay-item")
    assert rows.nth(1).locator(".overlay-size").get_attribute("aria-label") == "Text 2 size"
    assert rows.nth(1).locator(".text-effect").get_attribute("aria-label") == "Text 2 effect"
    assert rows.nth(0).locator(".overlay-font").get_attribute("aria-label") == "Text 1 font"
    image = page.locator(".image-overlay-item").first
    assert image.locator(".image-overlay-opacity").get_attribute("aria-label") == "Image 1 opacity"
    # A visible label still moves focus to its control.
    page.click("label[for='watermarkSize']")
    assert page.evaluate("document.activeElement.id") == "watermarkSize"


def test_overlay_numbers_follow_the_rows_after_a_delete(page, tmp_path):
    upload(page, tmp_path)
    page.click('[data-section="textSection"]')
    for _ in range(3):
        page.click('[data-action="add-text"]')
    page.click('[aria-label="Delete text 1"]')
    sizes = page.locator(".overlay-size")
    assert [sizes.nth(i).get_attribute("aria-label") for i in range(2)] == ["Text 1 size", "Text 2 size"]


def test_switches_are_not_labels(page, tmp_path):
    upload(page, tmp_path)
    page.click('[data-section="wallpaperSection"]')
    switch = page.locator('[data-action="toggle-wallpaper"]')
    assert switch.evaluate("el => el.tagName") == "DIV"
    assert switch.get_attribute("role") == "switch"
    switch.focus()
    page.keyboard.press("Space")
    assert switch.get_attribute("aria-checked") == "true"
    assert "On" in switch.inner_text()
