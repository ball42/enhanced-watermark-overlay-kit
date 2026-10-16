"""Photo editor in a browser: the preview follows the controls."""

from tests.conftest import make_test_image


def upload(page, tmp_path):
    path = tmp_path / "photo.png"
    path.write_bytes(make_test_image(120, 80, (40, 120, 200)).getvalue())
    page.goto("/")
    page.set_input_files("#fileInput", str(path))
    page.wait_for_selector("#preview-image[src^='/api/original/']")


def drag(page, selector, fraction):
    slider = page.locator(selector)
    slider.scroll_into_view_if_needed()
    box = slider.bounding_box()
    y = box["y"] + box["height"] / 2
    page.mouse.move(box["x"] + box["width"] / 2, y)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * fraction, y, steps=5)
    page.mouse.up()


def test_moving_a_slider_updates_the_preview(page, tmp_path):
    upload(page, tmp_path)
    with page.expect_request(lambda r: r.url.endswith("/api/process") and r.method == "POST",
                             timeout=2000):
        drag(page, "#brightness", 0.8)
    page.wait_for_selector("#preview-image[src^='/api/preview/']", timeout=2000)
    assert page.locator("#brightnessValue").inner_text() != "100%"


def test_a_burst_of_changes_sends_one_render(page, tmp_path):
    upload(page, tmp_path)
    posts = []
    page.on("request", lambda r: posts.append(r) if r.url.endswith("/api/process") else None)
    for value in ("110", "120", "130", "140"):
        page.fill("#contrast", value)
    page.wait_for_selector("#preview-image[src^='/api/preview/']", timeout=2000)
    page.wait_for_timeout(600)
    assert len(posts) == 1
    assert '"contrast": 140' in posts[0].post_data.replace('":', '": ')


def test_the_button_still_renders_on_demand(page, tmp_path):
    upload(page, tmp_path)
    assert "Update preview" in page.inner_text("#processBtn")
    page.click("#processBtn")
    page.wait_for_selector("#preview-image[src^='/api/preview/']", timeout=2000)
