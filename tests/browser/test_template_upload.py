"""Template designer in a browser: a failed upload says why."""


def test_an_oversized_asset_upload_shows_the_size_limit(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.set_input_files("#assetFile", files=[{
        "name": "huge.png", "mimeType": "image/png", "buffer": b"\0" * (17 * 1024 * 1024)}])
    page.wait_for_function(
        "document.querySelector('#previewStatus').textContent.startsWith('Upload failed')")
    assert page.inner_text("#previewStatus") == "Upload failed: That file is larger than 16 MB."
