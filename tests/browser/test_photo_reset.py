"""Photo editor in a browser: Reset really starts over."""

from tests.browser.test_photo_live import upload


def open_section(page, name):
    header = page.locator(f'[data-section="{name}"]')
    if header.get_attribute("aria-expanded") != "true":
        header.click()


def test_reset_turns_switches_off_and_clears_the_watermark(page, tmp_path):
    upload(page, tmp_path)
    open_section(page, "wallpaperSection")
    open_section(page, "backgroundSection")
    open_section(page, "watermarkSection")
    for action in ("toggle-wallpaper", "toggle-background"):
        switch = page.locator(f'[data-action="{action}"]')
        switch.click()
        assert switch.get_attribute("aria-checked") == "true"
    page.select_option("#backgroundType", "gradient")
    page.fill("#watermarkText", "DRAFT")
    page.select_option("#watermarkPosition", "center")

    page.click("#resetBtn")

    for action in ("toggle-wallpaper", "toggle-background"):
        switch = page.locator(f'[data-action="{action}"]')
        assert switch.get_attribute("aria-checked") == "false"
        assert switch.locator(".toggle-state").inner_text() == "Off"
    assert page.input_value("#watermarkText") == ""
    assert page.input_value("#watermarkPosition") == "bottom-right"
    assert page.input_value("#watermarkSize") == "24"
    assert page.input_value("#backgroundType") == "color"
    assert page.is_hidden("#gradientOptions")


def test_after_reset_a_new_upload_has_no_watermark(page, tmp_path):
    upload(page, tmp_path)
    open_section(page, "watermarkSection")
    page.fill("#watermarkText", "DRAFT")
    page.click("#resetBtn")
    upload(page, tmp_path, reload=False)  # the same file again, on the same page
    with page.expect_request(lambda r: r.url.endswith("/api/process")) as info:
        page.click("#processBtn")
    assert '"watermark":null' in info.value.post_data
