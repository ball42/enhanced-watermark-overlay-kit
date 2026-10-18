"""Template designer in a browser: Undo and Redo."""

import pytest


@pytest.fixture()
def designer(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    return page


def layers(page):
    return page.evaluate("JSON.parse(localStorage.getItem('ewok-template-draft') || 'null')")["layers"]


def wait_layers(page, n):
    page.wait_for_function(f"document.querySelectorAll('#layerList > li').length === {n}")


def test_undo_and_redo_buttons_start_disabled(designer):
    assert designer.is_disabled("#undoButton") and designer.is_disabled("#redoButton")


def test_undo_brings_back_a_deleted_layer_and_redo_deletes_it_again(designer):
    page = designer
    page.fill("#tplName", "Lobby")  # an edit, so the draft holds the template
    before = layers(page)

    page.click('[aria-label="Delete layer 2"]')
    wait_layers(page, 1)
    page.click("#layersHeading")  # focus out of any field
    page.keyboard.press("ControlOrMeta+z")
    wait_layers(page, 2)
    assert layers(page) == before
    assert page.inner_text("#layerList > li:nth-child(2) .layer-select").startswith("2. QR: jamf-device:")

    page.keyboard.press("ControlOrMeta+Shift+z")
    wait_layers(page, 1)
    page.click("#undoButton")
    wait_layers(page, 2)
    page.click("#redoButton")
    wait_layers(page, 1)


def test_undo_puts_a_dragged_box_back(designer):
    page = designer
    start = {"x": 0.1, "y": 0.6, "w": 0.8, "h": 0.05}
    frame = page.locator('#overlay .tpl-boxframe[data-index="0"]')
    frame.scroll_into_view_if_needed()
    box = frame.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.down()
    for step in range(1, 6):
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2 - 12 * step)
    page.mouse.up()
    page.wait_for_function("!document.querySelector('#undoButton').disabled")
    assert layers(page)[0]["box"]["y"] < start["y"]

    page.click("#undoButton")
    page.wait_for_function(
        "y => JSON.parse(localStorage.getItem('ewok-template-draft')).layers[0].box.y === y", arg=start["y"])
    assert layers(page)[0]["box"] == start
    # One drag is one step: nothing older to undo.
    assert page.is_disabled("#undoButton")


def test_ctrl_z_in_the_text_field_undoes_only_the_typing(designer):
    page = designer
    page.click('[aria-label="Delete layer 2"]')
    wait_layers(page, 1)
    page.click("#propText")
    page.keyboard.press("End")
    page.keyboard.type("XY")
    page.wait_for_function("document.querySelector('#propText').value.endsWith('XY')")
    page.keyboard.press("ControlOrMeta+z")
    page.wait_for_timeout(500)
    # The browser undid typing in the field; the designer's undo did not run.
    assert not page.input_value("#propText").endswith("XY")
    assert page.locator("#layerList > li").count() == 1
    assert page.is_disabled("#redoButton")
