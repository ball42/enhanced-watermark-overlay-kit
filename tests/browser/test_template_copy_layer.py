"""Template designer in a browser: Copy makes a matching layer below the original."""

import json

STYLED = {
    "schema_version": 1, "name": "Styled", "canvas": {"width": 1290, "height": 2796},
    "background": {"color": "#0B2545"},
    "layers": [
        {"type": "panel", "box": {"x": 0.05, "y": 0.4, "w": 0.9, "h": 0.3}, "color": "#000000", "opacity": 0.5},
        {"type": "text", "text": "Asset {{asset_tag}}", "box": {"x": 0.1, "y": 0.45, "w": 0.7, "h": 0.04},
         "size": 0.02, "color": "#FFD166", "align": "left", "overflow": "ellipsis", "hide_if_empty": True},
    ],
}


def draft(page):
    return json.loads(page.evaluate("localStorage.getItem('ewok-template-draft')"))["template"]


def test_copy_adds_the_same_layer_below_it_and_selects_it(page):
    page.add_init_script(
        f"localStorage.setItem('ewok-template-draft', {json.dumps(json.dumps(STYLED))});")
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")

    page.click('[aria-label="Copy layer 2"]')
    page.wait_for_function("document.querySelectorAll('#layerList > li').length === 3")
    layers = draft(page)["layers"]
    source, copy = layers[1], layers[2]
    assert {k: v for k, v in copy.items() if k != "box"} == {k: v for k, v in source.items() if k != "box"}
    assert copy["box"] == {"x": 0.1, "y": 0.51, "w": 0.7, "h": 0.04}
    assert page.get_attribute("#layerList > li:nth-child(3) .layer-select", "aria-pressed") == "true"
    assert page.input_value("#propText") == "Asset {{asset_tag}}"
    page.wait_for_function("!document.querySelector('.tpl-preview').classList.contains('is-stale')")


def test_a_copy_at_the_bottom_stays_inside_the_canvas(page):
    low = json.loads(json.dumps(STYLED))
    low["layers"][1]["box"]["y"] = 0.95
    page.add_init_script(
        f"localStorage.setItem('ewok-template-draft', {json.dumps(json.dumps(low))});")
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.click('[aria-label="Copy layer 2"]')
    page.wait_for_function("document.querySelectorAll('#layerList > li').length === 3")
    assert draft(page)["layers"][2]["box"]["y"] == 0.96


def test_layer_rows_fit_a_phone_screen(page):
    """Four buttons per row: on a 390 px screen they wrap under the name
    instead of widening the page."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    row = page.locator("#layerList > li").first.bounding_box()
    assert row["x"] + row["width"] <= 390
