"""Template designer in a browser: a preview that cannot render says so on
every problem, apart from warnings on a render that worked."""

import json

OUTSIDE = {
    "schema_version": 1,
    "name": "Box outside",
    "canvas": {"width": 1290, "height": 2796},
    "background": {"color": "#0B2545"},
    "layers": [
        {"type": "text", "text": "{{device_name}}", "box": {"x": 0.6, "y": 0.5, "w": 0.8, "h": 0.05},
         "size": 0.028, "color": "#FFFFFF", "align": "center"},
    ],
}

LABEL = "el => getComputedStyle(el, '::before').content"


def open_with_draft(page, template):
    page.add_init_script(
        f"localStorage.setItem('ewok-template-draft', {json.dumps(json.dumps(template))});")
    page.goto("/template")


def test_a_box_outside_the_canvas_is_labelled_not_rendered(page):
    open_with_draft(page, OUTSIDE)
    page.wait_for_function("document.querySelector('#previewStatus').textContent.startsWith('Not rendered')")
    item = page.locator("#warningList li").first
    assert "outside" in item.inner_text() or "canvas" in item.inner_text()
    label = item.evaluate(LABEL)
    assert "Not rendered:" in label and "Warning" not in label
    assert "✕" in label  # ✕, not the warning's ⚠
    assert "is-blocked" in item.get_attribute("class")
    badge = page.locator("#warningCount")
    assert "Not rendered" in badge.inner_text()
    assert badge.locator("i.fa-circle-xmark").count() == 1


def test_a_render_that_worked_keeps_the_warning_label(page):
    fixed = json.loads(json.dumps(OUTSIDE))
    fixed["layers"][0]["box"]["x"] = 0.1
    fixed["layers"][0]["text"] = "{{asset_tag}}"
    open_with_draft(page, fixed)
    page.wait_for_selector("#previewImage:not([hidden])")
    page.select_option("#samplePreset", "2")  # no asset tag: a warning
    page.wait_for_function("document.querySelector('#warningList li.rb-alert--warn')")
    label = page.locator("#warningList li").first.evaluate(LABEL)
    assert "Warning:" in label and "Not rendered" not in label
