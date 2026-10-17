"""Photo editor in a browser: a slow render is never piled up behind more renders."""

import time

import views.api

from tests.browser.test_photo_live import upload


def test_edits_during_a_slow_render_send_one_more_render_not_one_each(page, tmp_path, monkeypatch):
    real = views.api.add_watermark

    def slow_watermark(*args, **kwargs):
        time.sleep(1.5)
        return real(*args, **kwargs)

    monkeypatch.setattr(views.api, "add_watermark", slow_watermark)
    upload(page, tmp_path)

    sent, in_flight, most = [], [0], [0]

    def on_request(r):
        if r.url.endswith("/api/process"):
            sent.append(r)
            in_flight[0] += 1
            most[0] = max(most[0], in_flight[0])

    def on_done(r):
        if r.url.endswith("/api/process"):
            in_flight[0] -= 1

    page.on("request", on_request)
    page.on("requestfinished", on_done)
    page.on("requestfailed", on_done)

    for value in ("110", "120", "130", "140", "150"):
        page.fill("#contrast", value)
        page.wait_for_timeout(450)
    page.wait_for_function("!document.querySelector('#preview-image').classList.contains('is-stale')",
                           timeout=10000)
    page.wait_for_timeout(600)

    assert most[0] <= 1
    assert len(sent) <= 2, [r.post_data for r in sent]
    # The last render carries the last edit.
    assert sent[-1].post_data_json["contrast"] == 150
    shown = page.get_attribute("#preview-image", "src")
    assert shown.startswith("/api/preview/processed_")
