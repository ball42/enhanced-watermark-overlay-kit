"""Template designer in a browser: Hide leaves a layer out of the preview,
but the export still has it."""

import json

PANEL = {"type": "panel", "box": {"x": 0.05, "y": 0.45, "w": 0.9, "h": 0.2},
         "color": "#0B2545", "opacity": 0.6, "radius": 0.12}


def with_panel():
    return {
        "schema_version": 1, "name": "Panel", "canvas": {"width": 1290, "height": 2796},
        "background": {"color": "#FFFFFF"},
        "layers": [
            PANEL,
            {"type": "text", "text": "{{device_name}}", "box": {"x": 0.1, "y": 0.5, "w": 0.8, "h": 0.05},
             "size": 0.028, "color": "#FFFFFF", "align": "center"},
            {"type": "qr", "data": "jamf-device:{{jss_id}}", "box": {"x": 0.35, "y": 0.7, "w": 0.3, "h": 0.14}},
        ],
    }


def open_designer(page):
    page.add_init_script(
        f"localStorage.setItem('ewok-template-draft', {json.dumps(json.dumps(with_panel()))});")
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")


def preview_after(page, action):
    with page.expect_request(lambda r: r.url.endswith("/api/template/preview")
                             and r.method == "POST") as info:
        action()
    return info.value.post_data_json["template"]


def exported(page):
    with page.expect_download() as info:
        page.click("#downloadPackage")
    return json.loads(open(info.value.path()).read())


def test_hide_leaves_the_panel_out_of_the_preview_but_not_the_export(page):
    open_designer(page)
    toggle = page.locator('[aria-label="Hide layer 1"]')
    assert toggle.inner_text() == "Hide"
    assert toggle.get_attribute("aria-pressed") == "false"

    sent = preview_after(page, toggle.click)
    assert sent["layers"][0] == {"type": "panel", "box": PANEL["box"], "opacity": 0}
    assert sent["layers"][1]["type"] == "text"  # layer numbers stay as listed
    assert toggle.inner_text() == "Show"
    assert toggle.get_attribute("aria-pressed") == "true"
    assert page.inner_text("#layerList li:nth-child(1) .layer-select").endswith("(hidden)")
    assert "is-hidden" in page.get_attribute('#overlay .tpl-boxframe[data-index="0"]', "class")
    assert page.inner_text("#ioStatus") == "1 layer is hidden in the preview; it is still exported."

    package = exported(page)
    layers = package.get("template", package)["layers"]
    assert layers[0] == PANEL

    sent = preview_after(page, toggle.click)
    assert sent["layers"][0] == PANEL
    assert toggle.inner_text() == "Hide"
    assert page.inner_text("#ioStatus") == "Downloaded panel.brander.json: upload it to JAWA's template store."


def test_hiding_is_not_an_edit(page):
    open_designer(page)
    page.click('[aria-label="Hide layer 1"]')
    page.wait_for_selector(".tpl-preview:not(.is-stale)")
    assert page.is_disabled("#undoButton")
