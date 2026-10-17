"""Photo editor in a browser: after an upload expires, the same photo can be chosen again."""

import json

from tests.conftest import make_test_image


def test_the_same_photo_can_be_chosen_again_after_it_expired(page, tmp_path):
    path = tmp_path / "photo.png"
    path.write_bytes(make_test_image(120, 80, (40, 120, 200)).getvalue())
    page.goto("/")
    page.set_input_files("#fileInput", str(path))
    page.wait_for_selector("#preview-image[src^='/api/original/']")

    expired = "This upload expired after an hour without use. Upload it again."
    page.route("**/api/process", lambda route: route.fulfill(
        status=410, content_type="application/json", body=json.dumps({"error": expired})))
    page.click("#processBtn")
    page.wait_for_function("document.querySelector('#processBtn').disabled")
    # Chromium fires no change event for the file that is already selected,
    # so the input must be empty for the same photo to upload again.
    assert page.eval_on_selector("#fileInput", "el => el.value") == ""

    page.unroute("**/api/process")
    with page.expect_response(lambda r: r.url.endswith("/api/upload")):
        page.set_input_files("#fileInput", str(path))
    page.wait_for_function("!document.querySelector('#processBtn').disabled")
    page.click("#processBtn")
    page.wait_for_selector("#preview-image[src^='/api/preview/']", timeout=3000)
