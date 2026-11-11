"""Template designer in a browser: uploading a file whose asset id is
already in the library asks before it replaces that asset."""

import io

from PIL import Image

from tests.browser.test_template_asset_delete import open_designer, uses_logo


def png(color):
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), color).save(buf, "PNG")
    return buf.getvalue()


def served_color(page, asset_id):
    data = page.request.get(f"/api/template/assets/{asset_id}").body()
    return Image.open(io.BytesIO(data)).convert("RGB").getpixel((0, 0))


def upload(page, name, color):
    page.set_input_files("#assetFile", files=[
        {"name": name, "mimeType": "image/png", "buffer": png(color)}])


def test_cancel_keeps_the_used_asset(page):
    open_designer(page, uses_logo())
    messages = []
    page.once("dialog", lambda d: (messages.append(d.message), d.dismiss()))
    upload(page, "Logo.png", (0, 0, 255))
    page.wait_for_function(
        "document.querySelector('#assetStatus').textContent.startsWith('Not uploaded')")
    assert messages == [
        "logo is already in the library and is used by the background and layer 3. Replace it?"]
    assert served_color(page, "logo") == (200, 30, 30)


def test_confirm_replaces_the_asset(page):
    open_designer(page, uses_logo())
    page.once("dialog", lambda d: d.accept())
    upload(page, "logo.png", (0, 0, 255))
    page.wait_for_function(
        "document.querySelector('#assetStatus').textContent === 'Replaced asset logo.'")
    assert served_color(page, "logo") == (0, 0, 255)


def test_an_unused_existing_id_still_asks(page):
    open_designer(page, uses_logo())
    messages = []
    page.once("dialog", lambda d: (messages.append(d.message), d.dismiss()))
    upload(page, "spare.png", (0, 0, 255))
    page.wait_for_function(
        "document.querySelector('#assetStatus').textContent.startsWith('Not uploaded')")
    assert messages == ["spare is already in the library. Replace it?"]


def test_a_new_name_uploads_without_asking(page):
    open_designer(page, uses_logo())
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    upload(page, "New Badge.png", (0, 0, 255))
    page.wait_for_function(
        "document.querySelector('#assetStatus').textContent === 'Uploaded asset new-badge.'")
    assert dialogs == []
