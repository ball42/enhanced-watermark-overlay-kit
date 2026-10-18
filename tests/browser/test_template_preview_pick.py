"""Template designer in a browser: the preview says what it shows."""


def test_the_device_picker_is_on_the_first_screen_and_named_in_the_status(page):
    page.set_viewport_size({"width": 1280, "height": 800})
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    box = page.locator("#samplePreset").bounding_box()
    assert box["y"] + box["height"] <= 800
    page.select_option("#samplePreset", "1")
    page.wait_for_function(
        "document.querySelector('#previewStatus').textContent.includes('Ward 3')")
    assert page.inner_text("#previewStatus") == "Rendered 1290×2796 with iPad (Ward 3 iPad)."


def test_the_role_picker_shows_with_role_variants_and_is_named(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    assert not page.is_visible("#previewRole")
    page.check("#rolesOn")
    page.click("#addVariant")
    assert page.is_visible("#previewRole")
    page.select_option("#previewRole", "Role 1")
    page.wait_for_function(
        "document.querySelector('#previewStatus').textContent.includes('as Role 1')")
    assert page.inner_text("#previewStatus") == (
        "Rendered 1290×2796 with iPhone (Front Desk iPhone), as Role 1.")
