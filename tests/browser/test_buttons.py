"""Both pages in a browser: three button weights from roster, with Delete set
apart as an error outline that carries an icon and the word."""

import json

from tests.browser.test_photo_live import upload
from tests.browser.test_template_copy_layer import STYLED

WEIGHT = """(el) => {
  const s = getComputedStyle(el);
  return {bg: s.backgroundColor, border: s.borderTopColor, color: s.color, margin: s.marginTop};
}"""


def open_with_layers(page):
    page.add_init_script(
        f"localStorage.setItem('ewok-template-draft', {json.dumps(json.dumps(STYLED))});")
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")


def test_layer_rows_have_icon_moves_and_a_worded_delete(page):
    open_with_layers(page)
    up = page.locator('[aria-label="Move layer 2 up"]')
    assert "rb-btn--ghost" in up.get_attribute("class")
    assert up.inner_text().strip() == ""  # icon only; the aria-label names it
    assert up.locator("i.fa-arrow-up").count() == 1

    delete = page.locator('[aria-label="Delete layer 2"]')
    assert "ewok-btn--danger" in delete.get_attribute("class")
    assert delete.inner_text().strip() == "Delete"
    assert delete.locator("i.fa-trash").count() == 1
    ghost, danger = up.evaluate(WEIGHT), delete.evaluate(WEIGHT)
    assert danger["border"] != ghost["border"]  # set apart, and by more than hue
    assert danger["bg"] == "rgba(0, 0, 0, 0)"  # an outline, not a solid fill


def test_adds_are_neutral_outlines_and_buttons_have_no_margin(page):
    open_with_layers(page)
    add = page.locator('[data-add="text"]')
    solid = page.locator("#downloadPackage")
    a, s = add.evaluate(WEIGHT), solid.evaluate(WEIGHT)
    assert a["bg"] == "rgba(0, 0, 0, 0)" and s["bg"] != a["bg"]
    for el in (add, solid, page.locator('[aria-label="Delete layer 1"]')):
        assert el.evaluate(WEIGHT)["margin"] == "0px"
    assert page.locator("#templateEditor .rb-btn:not(.rb-btn--outline):not(.rb-btn--ghost)").count() == 1


def test_photo_editor_has_one_solid_button(page, tmp_path):
    upload(page, tmp_path)
    solid = page.locator(".rb-btn:not(.rb-btn--outline):not(.rb-btn--ghost)")
    assert solid.count() == 1
    assert solid.first.get_attribute("id") == "downloadBtn"
    page.click('[data-section="textSection"]')
    page.click('[data-action="add-text"]')
    delete = page.locator('[data-action="remove-overlay"]')
    assert delete.inner_text().strip() == "Delete"
    assert "ewok-btn--danger" in delete.get_attribute("class")
