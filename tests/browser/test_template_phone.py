"""Template designer on a phone: no sideways scrolling, tappable checkboxes."""

import pytest


@pytest.fixture()
def phone(page):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.evaluate("document.querySelectorAll('details.tpl-section').forEach((d) => { d.open = true; })")
    return page


def test_the_designer_fits_a_phone_screen(phone):
    widths = phone.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    assert widths[0] == widths[1] == 390


def test_checkbox_and_radio_rows_are_44px_tap_targets(phone):
    heights = phone.evaluate("""() => [...document.querySelectorAll('.tpl-inline')]
      .filter((el) => el.getClientRects().length)
      .map((el) => [el.textContent.trim(), el.getBoundingClientRect().height])""")
    assert heights, "no visible .tpl-inline labels"
    small = [label for label, height in heights if height < 44]
    assert not small, f"labels under 44 px tall: {small}"


def test_the_desktop_layout_keeps_two_columns(page):
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto("/template")
    columns = page.evaluate("getComputedStyle(document.querySelector('.tpl-grid')).gridTemplateColumns")
    assert len(columns.split()) == 2
