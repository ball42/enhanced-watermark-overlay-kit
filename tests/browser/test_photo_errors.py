"""Photo editor in a browser: every failure is one plain sentence."""

import json

from tests.conftest import make_test_image

NOT_RUNNING = "EWOK is not running. Start it with uv run ewok."
UNEXPECTED = "EWOK hit an error; the log has details."


def uploaded(page, tmp_path):
    path = tmp_path / "photo.png"
    path.write_bytes(make_test_image(120, 80, (40, 120, 200)).getvalue())
    page.goto("/")
    page.set_input_files("#fileInput", str(path))
    page.wait_for_selector("#preview-image[src^='/api/original/']")
    return path


def failure(page):
    page.wait_for_selector("#statusMessage.status-error")
    toast = page.locator(".toast-error")
    toast.wait_for()
    return page.inner_text("#statusMessage"), toast.locator("span").first.inner_text().strip()


def test_server_down_says_ewok_is_not_running(page, tmp_path):
    uploaded(page, tmp_path)
    page.route("**/api/process", lambda route: route.abort())
    page.click("#processBtn")
    status, toast = failure(page)
    assert status == "Not processed: " + NOT_RUNNING
    assert toast == "Not processed: " + NOT_RUNNING
    assert "Failed to fetch" not in status + toast


def test_upload_with_server_down_says_ewok_is_not_running(page, tmp_path):
    path = tmp_path / "photo.png"
    path.write_bytes(make_test_image().getvalue())
    page.goto("/")
    page.route("**/api/upload", lambda route: route.abort())
    page.set_input_files("#fileInput", str(path))
    status, toast = failure(page)
    assert status == "Not uploaded: " + NOT_RUNNING
    assert "connection" not in toast


def test_a_reply_that_is_not_json_is_an_unexpected_error(page, tmp_path):
    uploaded(page, tmp_path)
    page.route("**/api/process", lambda route: route.fulfill(
        status=502, content_type="text/html", body="<html>Bad gateway</html>"))
    page.click("#processBtn")
    status, _ = failure(page)
    assert status == "Not processed: " + UNEXPECTED
    assert "Unexpected token" not in status


def test_the_500_message_is_shown_once_without_a_double_prefix(page, tmp_path):
    uploaded(page, tmp_path)
    page.route("**/api/process", lambda route: route.fulfill(
        status=500, content_type="application/json", body=json.dumps({"error": UNEXPECTED})))
    page.click("#processBtn")
    status, _ = failure(page)
    assert status == "Not processed: " + UNEXPECTED


def test_a_bad_setting_is_named(page, tmp_path):
    uploaded(page, tmp_path)
    # The page never sends a string, so change the request on its way out.
    def tamper(route):
        body = json.loads(route.request.post_data)
        body["opacity"] = "50"
        route.continue_(post_data=json.dumps(body))

    page.route("**/api/process", tamper)
    page.click("#processBtn")
    status, _ = failure(page)
    assert status == "Not processed: Image Opacity must be a number."
