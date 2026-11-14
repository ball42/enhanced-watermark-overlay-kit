"""Template designer in a browser: the rendered preview downloads as a PNG."""

import base64
import io
import json

from PIL import Image

from tests.test_preview_weight import PHOTO_TEMPLATE, grainy_photo


def test_download_preview_png_is_the_full_size_render(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.wait_for_function("!document.querySelector('#downloadPreview').disabled")
    rendered = page.get_attribute("#previewImage", "src")
    with page.expect_download() as info:
        page.click("#downloadPreview")
    download = info.value
    assert download.suggested_filename == "untitled-template-front-desk-iphone.png"
    data = download.path().read_bytes()
    assert data == base64.b64decode(rendered.split(",", 1)[1])  # the render, without the box outlines
    assert Image.open(io.BytesIO(data)).size == (1290, 2796)


def test_the_button_is_disabled_until_a_render_succeeds(page):
    page.route("**/api/template/preview", lambda route: route.abort())
    page.goto("/template")
    page.wait_for_function(
        "document.querySelector('#previewStatus').textContent.startsWith('Not rendered')")
    assert page.is_disabled("#downloadPreview")


def test_over_a_photo_the_preview_is_a_jpeg_and_the_download_a_lossless_png(page):
    resp = page.request.post("/api/template/assets", multipart={
        "id": "photo", "file": {"name": "photo.jpg", "mimeType": "image/jpeg", "buffer": grainy_photo()}})
    assert resp.ok
    template = dict(PHOTO_TEMPLATE, name="Photo")
    page.add_init_script(f"localStorage.setItem('ewok-template-draft', {json.dumps(json.dumps(template))});")
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.wait_for_function("!document.querySelector('#downloadPreview').disabled")
    assert page.get_attribute("#previewImage", "src").startswith("data:image/jpeg;base64,")
    with page.expect_download() as info:
        page.click("#downloadPreview")
    data = info.value.path().read_bytes()
    assert data.startswith(b"\x89PNG")
    with Image.open(io.BytesIO(data), formats=["PNG"]) as img:
        assert img.size == (1290, 2796)
