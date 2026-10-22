"""Template designer in a browser: the device picks follow the canvas."""


def picked(page):
    return page.eval_on_selector_all(".device-pick:checked", "els => els.map(e => e.value)")


def test_a_new_template_fits_its_default_devices(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.wait_for_function("document.querySelector('#deviceWarnings').textContent.trim() !== ''")
    assert "Fits every selected device." in page.inner_text("#deviceWarnings")
    assert picked(page) == ["iphone-6.7", "iphone-6.1"]


def test_the_canvas_preset_picks_its_devices_until_the_user_picks(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.select_option("#canvasPreset", "2732x2732")
    assert picked(page) == ["ipad-12.9", "ipad-10.9"]
    page.select_option("#canvasPreset", "1290x2796")
    assert picked(page) == ["iphone-6.7", "iphone-6.1"]

    page.click("#tabDevices")
    page.check('.device-pick[value="iphone-se"]')
    page.select_option("#canvasPreset", "2732x2732")
    assert picked(page) == ["iphone-6.7", "iphone-6.1", "iphone-se"]
