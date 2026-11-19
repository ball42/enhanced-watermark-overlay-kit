"""Keyboard focus stays in the layer list after Move, Copy and Delete,
and in the overlay list after a photo overlay's Delete."""

import json

import pytest

from .test_photo_live import upload

THREE = {
    "schema_version": 1, "name": "Three", "canvas": {"width": 1290, "height": 2796},
    "background": {"color": "#0B2545"},
    "layers": [
        {"type": "text", "text": f"Line {n}", "box": {"x": 0.1, "y": 0.1 * n, "w": 0.7, "h": 0.04},
         "size": 0.02, "color": "#FFFFFF", "align": "left"}
        for n in (1, 2, 3)
    ],
}

ACTIVE = "(() => { const a = document.activeElement; return a.getAttribute('aria-label') || a.textContent.trim(); })()"


def open_three(page, layers=None):
    t = dict(THREE, layers=layers if layers is not None else THREE["layers"])
    page.add_init_script(f"localStorage.setItem('ewok-template-draft', {json.dumps(json.dumps(t))});")
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")


def press(page, label):
    page.focus(f'[aria-label="{label}"]')
    page.keyboard.press("Enter")


@pytest.mark.parametrize("label, expected", [
    ("Move layer 1 down", "Move layer 2 down"),
    ("Move layer 3 up", "Move layer 2 up"),
    # At the top its Up is disabled, so focus takes the row's Down.
    ("Move layer 2 up", "Move layer 1 down"),
    # At the bottom its Down is disabled, so focus takes the row's Up.
    ("Move layer 2 down", "Move layer 3 up"),
])
def test_move_keeps_focus_on_the_layers_arrow(page, label, expected):
    open_three(page)
    press(page, label)
    assert page.evaluate(ACTIVE) == expected


def test_copy_focuses_the_copys_select_button(page):
    open_three(page)
    press(page, "Copy layer 1")
    page.wait_for_function("document.querySelectorAll('#layerList > li').length === 4")
    assert page.evaluate("document.activeElement === document.querySelector('#layerList > li:nth-child(2) .layer-select')")
    assert page.evaluate(ACTIVE).startswith("2. Text: Line 1")


def test_delete_focuses_the_next_layer_then_the_last_then_add_text(page):
    open_three(page)
    press(page, "Delete layer 2")
    assert page.evaluate(ACTIVE).startswith("2. Text: Line 3")
    press(page, "Delete layer 2")  # the last one: focus goes to the new last layer
    assert page.evaluate(ACTIVE).startswith("1. Text: Line 1")
    press(page, "Delete layer 1")
    assert page.evaluate("document.activeElement.dataset.add") == "text"


def open_photo_sections(page):
    for section in ("textSection", "imageOverlaySection"):
        page.click(f'[data-section="{section}"]')


def test_photo_overlay_delete_focuses_the_next_row_or_add(page, tmp_path):
    upload(page, tmp_path)
    open_photo_sections(page)
    for _ in range(2):
        page.click('[data-action="add-text"]')
    page.focus('[aria-label="Delete text 1"]')
    page.keyboard.press("Enter")
    # The second row is now the first, and has its Delete.
    assert page.evaluate(ACTIVE) == "Delete text 1"
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.dataset.action") == "add-text"

    page.click('[data-action="add-image-overlay"]')
    page.focus('[aria-label="Delete image 1"]')
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.dataset.action") == "add-image-overlay"
