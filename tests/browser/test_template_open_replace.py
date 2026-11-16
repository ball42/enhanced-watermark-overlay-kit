"""Template designer in a browser: opening a package whose logo id is
already in the library asks first. Cancel keeps the library's file byte for
byte; OK replaces it and Undo puts the library's copy back."""

import base64
import json

from tests.browser.test_template_asset_delete import open_designer, uses_logo
from tests.browser.test_template_asset_replace import png, served_color


def open_package(page):
    package = {"kind": "brander-template", "format": 1, "name": "Theirs", "template": uses_logo(),
               "assets": {"logo": base64.b64encode(png((0, 0, 255))).decode()}}
    page.set_input_files("#openTemplate", files=[
        {"name": "theirs.brander.json", "mimeType": "application/json",
         "buffer": json.dumps(package).encode()}])


def status_starts(page, text):
    page.wait_for_function(
        f"document.querySelector('#ioStatus').textContent.startsWith({json.dumps(text)})")


def test_cancel_keeps_the_library_logo_byte_for_byte(page):
    open_designer(page, uses_logo())
    before = page.request.get("/api/template/assets/logo").body()
    messages = []
    page.once("dialog", lambda d: (messages.append(d.message), d.dismiss()))
    open_package(page)
    status_starts(page, "Opened theirs.brander.json.")
    assert messages == [
        "theirs.brander.json has its own logo. Replace the library's logo, used by the background "
        "and layer 3, for every template on this computer? Cancel keeps the library's copy."]
    assert "Kept your library assets: logo." in page.inner_text("#ioStatus")
    assert page.request.get("/api/template/assets/logo").body() == before


def test_ok_replaces_and_undo_puts_the_library_logo_back(page):
    open_designer(page, uses_logo())
    before = page.request.get("/api/template/assets/logo").body()
    page.once("dialog", lambda d: d.accept())
    open_package(page)
    status_starts(page, "Opened theirs.brander.json.")
    assert "Replaced library assets: logo (the old copies stay in the trash for a day)." \
        in page.inner_text("#ioStatus")
    assert "Added assets" not in page.inner_text("#ioStatus")
    assert served_color(page, "logo") == (0, 0, 255)
    page.click("[aria-label=\"Put back the library's logo\"]")
    status_starts(page, "Restored your library asset logo.")
    assert page.request.get("/api/template/assets/logo").body() == before


def test_the_undo_fits_a_phone(page):
    page.set_viewport_size({"width": 390, "height": 844})
    open_designer(page, uses_logo())
    page.once("dialog", lambda d: d.accept())
    open_package(page)
    status_starts(page, "Opened theirs.brander.json.")
    assert page.evaluate("document.documentElement.scrollWidth") == 390
    box = page.locator("[aria-label=\"Put back the library's logo\"]").bounding_box()
    assert box["height"] >= 44 and box["x"] + box["width"] <= 390
