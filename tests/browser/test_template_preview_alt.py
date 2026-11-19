"""Template designer in a browser: the preview image says what the wallpaper says."""


def alt(page):
    return page.get_attribute("#previewImage", "alt")


def test_the_preview_alt_follows_the_sample_device_name(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.wait_for_function("document.querySelector('#previewImage').alt.includes('Front Desk iPhone')")
    assert alt(page).startswith("1290×2796 wallpaper: text 'Front Desk iPhone'")
    page.fill("#sample-device_name", "Library Cart 9")
    page.wait_for_function("document.querySelector('#previewImage').alt.includes('Library Cart 9')")
    assert "Front Desk iPhone" not in alt(page)
    # The accessible name a screen reader reads is the new one.
    snapshot = page.locator("#previewImage").aria_snapshot()
    assert "Library Cart 9" in snapshot
