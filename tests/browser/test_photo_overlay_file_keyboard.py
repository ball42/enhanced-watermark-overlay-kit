"""Photo editor: an image overlay's Choose Image is reachable by keyboard,
opens the file picker on Enter or Space, and says which row it belongs to."""

import pytest

from .test_photo_live import upload


def add_overlay(page, tmp_path):
    upload(page, tmp_path)
    page.click('[data-section="imageOverlaySection"]')
    page.click('[data-action="add-image-overlay"]')


@pytest.mark.parametrize("key", ["Enter", "Space"])
def test_tab_from_delete_reaches_choose_image_and_opens_picker(page, tmp_path, key):
    add_overlay(page, tmp_path)
    page.focus('[aria-label="Delete image 1"]')
    page.keyboard.press("Tab")
    focused = page.evaluate(
        "({cls: document.activeElement.className, name: document.activeElement.getAttribute('aria-label')})")
    assert focused == {"cls": "image-overlay-file", "name": "Image 1 image file"}
    with page.expect_file_chooser() as chooser:
        page.keyboard.press(key)
    assert chooser.value.element.get_attribute("aria-label") == "Image 1 image file"


def test_choose_image_name_follows_the_row_after_a_delete(page, tmp_path):
    add_overlay(page, tmp_path)
    page.click('[data-action="add-image-overlay"]')
    page.click('[aria-label="Delete image 1"]')
    assert page.locator(".image-overlay-file").get_attribute("aria-label") == "Image 1 image file"


def test_focused_choose_image_shows_a_ring(page, tmp_path):
    add_overlay(page, tmp_path)
    page.focus('[aria-label="Delete image 1"]')
    page.keyboard.press("Tab")
    outline = page.locator(".image-upload-btn").evaluate("el => getComputedStyle(el).outlineStyle")
    assert outline == "solid"
