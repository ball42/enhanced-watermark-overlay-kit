"""Template designer in a browser: the preview stays in view while editing."""

import re

import pytest

STAGE_IN_VIEW = """() => {
  const bar = document.querySelector('.tpl-actionbar').getBoundingClientRect();
  const r = document.querySelector('#stage').getBoundingClientRect();
  return r.height > 100 && r.top >= bar.bottom - 1 && r.bottom <= window.innerHeight + 1;
}"""


@pytest.fixture()
def designer(page):
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    return page


@pytest.mark.parametrize("target", ["#canvasSection", "#assetsSection", "#layerList", "#propText",
                                    "#rolesSection", "#valuesSection", "#fleetFile"])
def test_the_stage_stays_in_view_while_a_section_is_edited(designer, target):
    page = designer
    page.evaluate("document.querySelectorAll('details.tpl-section').forEach((d) => { d.open = true; })")
    page.evaluate(f"document.querySelector('{target}').scrollIntoView({{block: 'center'}})")
    page.wait_for_timeout(100)
    assert page.evaluate(STAGE_IN_VIEW)


def test_the_warning_count_sits_by_the_stage(designer):
    page = designer
    page.fill("#sample-device_name", "W" * 48)
    page.wait_for_function("/^\\d+ warnings?$/.test(document.querySelector('#warningCount').textContent.trim())")
    page.fill("#sample-device_name", "iPad")
    page.wait_for_function("document.querySelector('#warningCount').textContent.trim() === 'No warnings'")


def test_devices_and_stress_renders_sit_in_tabs_under_the_stage(designer):
    page = designer
    assert page.is_visible("#warningList")
    assert not page.is_visible("#deviceGrid figure")
    page.click("#tabDevices")
    assert page.get_attribute("#tabDevices", "aria-selected") == "true"
    page.wait_for_selector("#deviceGrid figure", state="visible")
    assert not page.is_visible("#warningList")
    page.click("#tabStress")
    page.check("#stressToggle")
    page.wait_for_selector("#stressRenders figure", state="visible")
    page.focus("#tabStress")
    page.keyboard.press("ArrowLeft")  # arrow keys move between tabs
    assert page.get_attribute("#tabDevices", "aria-selected") == "true"


def test_canvas_assets_roles_and_sample_sections_collapse(designer):
    page = designer
    for sel in ("#canvasSection", "#assetsSection", "#rolesSection", "#valuesSection"):
        assert page.evaluate(f"document.querySelector('{sel}').tagName") == "DETAILS"
    assert not page.is_visible("#rolesOn")
    page.click("#rolesSection > summary")
    assert page.is_visible("#rolesOn")


def test_the_selected_layers_properties_open_under_it(designer):
    page = designer
    assert page.locator("#layerList > li:nth-child(1) #propsSection").count() == 1
    page.click("#layerList > li:nth-child(2) .layer-select")
    assert page.locator("#layerList > li:nth-child(2) #propsSection").count() == 1
    page.click("#layerList > li:nth-child(1) .layer-select")
    page.click("#propText")
    page.keyboard.type(" here")
    page.wait_for_timeout(100)
    # Typing redraws the layer names but keeps the field focused.
    assert page.evaluate("document.activeElement.id") == "propText"
    assert page.input_value("#propText").endswith(" here")
    assert "here" in page.inner_text("#layerList > li:nth-child(1) .layer-select")


def test_headings_in_both_columns_align_the_same(designer):
    page = designer
    align = "(sel) => getComputedStyle(document.querySelector(sel)).textAlign"
    assert re.match("left|start", page.evaluate(align, "#previewHeading"))
    assert page.evaluate(align, "#previewHeading") == page.evaluate(align, "#layersHeading")
