"""Photo editor in a browser: a second upload replaces the first photo's result."""

from tests.conftest import make_test_image


def choose(page, path):
    with page.expect_response(lambda r: r.url.endswith("/api/upload")) as info:
        page.set_input_files("#fileInput", str(path))
    return info.value.json()["filename"]


def test_a_second_upload_shows_the_new_photo(page, tmp_path):
    first = tmp_path / "a.png"
    first.write_bytes(make_test_image(120, 80, (40, 120, 200)).getvalue())
    second = tmp_path / "b.png"
    second.write_bytes(make_test_image(90, 60, (200, 60, 40)).getvalue())

    page.goto("/")
    choose(page, first)
    page.click("#processBtn")
    page.wait_for_selector("#preview-image[src^='/api/preview/']", timeout=2000)
    assert page.locator("#downloadSection").is_visible()

    with page.expect_response(lambda r: r.url.endswith("/api/process"), timeout=3000) as render:
        b_name = choose(page, second)
        # Before the new render: the new photo itself, and no stale Download.
        page.wait_for_selector(f"#preview-image[src='/api/original/{b_name}']", timeout=2000)
        assert not page.locator("#downloadSection").is_visible()

    # The render that follows is made from photo B.
    assert render.value.request.post_data_json["filename"] == b_name
    processed = render.value.json()["processed_filename"]
    page.wait_for_selector(f"#preview-image[src='/api/preview/{processed}']", timeout=2000)
    assert page.locator("#downloadSection").is_visible()
