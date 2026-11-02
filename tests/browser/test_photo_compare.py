"""Photo editor in a browser: hold a button to compare with the original."""

from tests.browser.test_photo_live import upload


def process(page):
    page.click("#processBtn")
    page.wait_for_selector("#preview-image[src^='/api/preview/']")


def src(page):
    return page.get_attribute("#preview-image", "src")


def test_the_button_appears_only_after_a_process(page, tmp_path):
    upload(page, tmp_path)
    assert page.is_hidden("#compareBtn")
    process(page)
    assert page.is_visible("#compareBtn")
    assert page.inner_text("#compareBtn").strip() == "Hold to see original"


def test_holding_the_button_shows_the_original(page, tmp_path):
    upload(page, tmp_path)
    process(page)
    processed = src(page)
    page.hover("#compareBtn")
    page.mouse.down()
    assert src(page).startswith("/api/original/")
    assert page.inner_text("#compareBtn").strip() == "Showing original"
    page.mouse.up()
    assert src(page) == processed
    assert page.inner_text("#compareBtn").strip() == "Hold to see original"


def test_holding_space_shows_the_original(page, tmp_path):
    upload(page, tmp_path)
    process(page)
    processed = src(page)
    page.focus("#compareBtn")
    page.keyboard.down(" ")
    assert src(page).startswith("/api/original/")
    page.keyboard.up(" ")
    assert src(page) == processed


def test_a_new_upload_hides_the_button(page, tmp_path):
    upload(page, tmp_path)
    process(page)
    upload(page, tmp_path, reload=False)
    assert page.is_hidden("#compareBtn")
