"""Template designer in a browser: the device check keeps two chunks in flight."""

import json
import statistics
import time

import pytest

# Server CPU per device for the default template (render, lint, thumbnail):
# 32 to 33 ms here at load 350 to 400. Rendering each device twice measured
# 61.5, so the bound fails a 2x slowdown with room for a slower machine.
BUDGET_CPU_MS = 48



@pytest.fixture()
def designer(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    return page


def devices_csv(tmp_path, n):
    csv = tmp_path / "fleet.csv"
    csv.write_text("device_name\r\n" + "".join(f"iPad {k}\r\n" for k in range(1, n + 1)))
    return csv


def test_two_chunks_go_out_at_once_and_stop_cancels_both(designer, tmp_path):
    page = designer
    held = []
    page.route("**/api/template/preview-batch", lambda r: held.append(r))  # nothing answers
    page.set_input_files("#fleetFile", str(devices_csv(tmp_path, 45)))
    page.wait_for_function("document.querySelector('#fleetProgress') && !document.querySelector('#fleetProgress').hidden")
    deadline = time.monotonic() + 5
    while len(held) < 2 and time.monotonic() < deadline:
        page.wait_for_timeout(50)
    page.wait_for_timeout(300)  # no third chunk goes out while two are waiting
    assert sorted(json.loads(r.request.post_data)["first"] for r in held) == [1, 11]

    failed = []
    page.on("requestfailed", lambda req: failed.append(json.loads(req.post_data)["first"]))
    page.click("#fleetStop")
    page.wait_for_selector("#fleetProgress", state="hidden")
    page.wait_for_timeout(200)
    assert sorted(failed) == [1, 11]  # both in-flight chunks were cancelled
    assert page.text_content("#fleetStatus") == "Stopped before any device was checked."
    assert len(held) == 2
    page.unroute_all(behavior="ignoreErrors")


def test_a_later_chunk_landing_first_still_lists_in_file_order(designer, tmp_path):
    page = designer
    held = []

    def route(r):
        if json.loads(r.request.post_data)["first"] == 1:
            held.append(r)  # the first chunk answers last
        else:
            r.continue_()

    page.route("**/api/template/preview-batch", route)
    page.set_input_files("#fleetFile", str(devices_csv(tmp_path, 25)))
    page.wait_for_function("document.querySelector('#fleetProgressText').textContent.startsWith('Checked 15 ')")
    names = page.locator("#fleetSheet .tpl-fleet-name").all_text_contents()
    assert names == [f"iPad {k}" for k in range(11, 26)]  # results fill in as each chunk lands
    held[0].continue_()
    page.wait_for_function("document.querySelector('#fleetStatus').textContent.startsWith('Checked 25 devices')")
    names = page.locator("#fleetSheet .tpl-fleet-name").all_text_contents()
    assert names == [f"iPad {k}" for k in range(1, 26)]
    page.unroute_all(behavior="ignoreErrors")


def test_a_failed_chunk_stops_the_others(designer, tmp_path):
    page = designer
    sent = []

    def route(r):
        first = json.loads(r.request.post_data)["first"]
        sent.append(first)
        if first == 11:
            r.fulfill(status=400, content_type="application/json", body=json.dumps({"error": "Broken."}))
        else:
            r.continue_()

    page.route("**/api/template/preview-batch", route)
    page.set_input_files("#fleetFile", str(devices_csv(tmp_path, 200)))
    page.wait_for_function("document.querySelector('#fleetStatus').textContent.startsWith('Not checked: Broken.')")
    page.wait_for_timeout(300)
    assert len(sent) <= 3  # chunks 1 and 11, and at most the one chunk 1's worker took next
    page.unroute_all(behavior="ignoreErrors")


# Each preview-batch the page sent: when the browser sent it and when the
# answer was in (ms on the page's clock), and the server's CPU time for it.
CHUNKS = """() => performance.getEntriesByType('resource')
  .filter(e => e.name.endsWith('/api/template/preview-batch'))
  .map(e => ({ start: e.startTime, end: e.responseEnd,
               cpu: (e.serverTiming.find(t => t.name === 'render') || {}).duration }))"""


def test_a_200_device_check_keeps_two_chunks_busy_and_renders_within_budget(designer, tmp_path):
    """A fixed wall-clock bound (6.5 s) failed on unchanged code whenever the
    shared machine was loaded (7.8 to 16.4 s at load 600), so the budget is
    made of two things load does not move: how many chunks the page keeps in
    flight, read from the browser's own timings, and the server's CPU time per
    device, which a busy machine does not inflate the way it does wall time."""
    page = designer
    page.set_input_files("#fleetFile", str(devices_csv(tmp_path, 200)))
    page.wait_for_function(
        "document.querySelector('#fleetStatus').textContent.startsWith('Checked 200 devices')", timeout=120000)
    chunks = page.evaluate(CHUNKS)
    assert len(chunks) == 20

    # Two in flight measured 1.97 at load 400; one at a time (FLEET_PARALLEL
    # = 1, a run about twice as long on an idle machine) measured 0.99.
    span = max(c["end"] for c in chunks) - min(c["start"] for c in chunks)
    in_flight = sum(c["end"] - c["start"] for c in chunks) / span
    assert in_flight >= 1.6, f"{in_flight:.2f} chunks in flight on average"

    # The server's CPU per device, median over the chunks after the first,
    # which also loads fonts and fills the render cache.
    per_device = statistics.median(c["cpu"] for c in chunks[1:]) / 10
    assert per_device <= BUDGET_CPU_MS, f"{per_device:.1f} ms of CPU per device"
