"""Template designer in a browser: the device check keeps two chunks in flight."""

import json
import time

import pytest


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


def test_a_200_device_check_of_the_default_template_finishes_quickly(designer, tmp_path):
    page = designer
    csv = devices_csv(tmp_path, 200)
    started = time.perf_counter()
    page.set_input_files("#fleetFile", str(csv))
    page.wait_for_function(
        "document.querySelector('#fleetStatus').textContent.startsWith('Checked 200 devices')", timeout=60000)
    took = time.perf_counter() - started
    # One chunk at a time took 8.2 s here before renders got faster; two at
    # once take about 3.5 s on a loaded machine. The bound leaves headroom.
    assert took < 6.5, f"200-device check took {took:.1f} s"
