"""Template designer in a browser: preview warnings name the right layer."""

import json

BLANK_IMAGE_FIRST = {
    "schema_version": 1,
    "name": "Blank image first",
    "canvas": {"width": 1290, "height": 2796},
    "background": {"color": "#0B2545"},
    "layers": [
        {"type": "image", "asset": "", "box": {"x": 0.35, "y": 0.3, "w": 0.3, "h": 0.14}},
        {"type": "text", "text": "{{asset_tag}}", "box": {"x": 0.1, "y": 0.5, "w": 0.8, "h": 0.05},
         "size": 0.028, "color": "#FFFFFF", "align": "center", "hide_if_empty": True},
    ],
}


def open_with_draft(page, template):
    page.add_init_script(
        f"localStorage.setItem('ewok-template-draft', {json.dumps(json.dumps(template))});")
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")


def wait_for_warning(page, text):
    page.wait_for_function(
        "t => document.querySelector('#warningList').textContent.includes(t)", arg=text)


def test_a_blank_image_layer_above_text_keeps_the_layer_number(page):
    open_with_draft(page, BLANK_IMAGE_FIRST)
    page.select_option("#samplePreset", "2")  # no asset tag
    wait_for_warning(page, "hidden because")
    text = page.inner_text("#warningList")
    assert "ayer 2" in text and "ayer 1" not in text
