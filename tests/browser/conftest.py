"""Browser tests: the real pages in headless Chromium against a local server.

They need the "browser" dependency group and Playwright's Chromium:

    uv sync --group browser
    uv run playwright install chromium
    uv run pytest tests/browser

Without Playwright they are skipped.
"""

import os
import threading

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

PORT = int(os.environ.get("EWOK_TEST_PORT", "8406"))


@pytest.fixture()
def live_url(app):
    server = make_server("127.0.0.1", PORT, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{PORT}"
    server.shutdown()
    thread.join()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        try:
            chromium = p.chromium.launch()
        except Exception as exc:  # no browser installed
            pytest.skip(f"Chromium is not available: {exc}")
        yield chromium
        chromium.close()


@pytest.fixture()
def page(browser, live_url):
    context = browser.new_context(base_url=live_url)
    # Stay local: fonts and icons from CDNs are not needed for these checks.
    context.route("**/*", lambda route: route.continue_()
                  if route.request.url.startswith(live_url) else route.abort())
    tab = context.new_page()
    yield tab
    context.close()
