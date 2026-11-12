"""Template designer in a browser: check the template against devices from a CSV."""

import json

import pytest

CSV = ("device_name,asset_tag,jss_id,location.building\r\n"
       "Front Desk iPhone,HR-1,1,North\r\n"
       + "W" * 48 + ",HR-2,2,South\r\n"
       "Lab iPad,HR-3,3,\"East, Wing\"\r\n")


@pytest.fixture()
def designer(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    return page


def test_csv_devices_show_as_thumbnails_with_warnings_first(designer, tmp_path):
    page = designer
    csv = tmp_path / "fleet.csv"
    csv.write_text(CSV)
    page.set_input_files("#fleetFile", str(csv))
    page.wait_for_function("document.querySelectorAll('#fleetSheet .tpl-fleet-pick').length === 3")
    names = page.locator("#fleetSheet .tpl-fleet-name").all_text_contents()
    assert names[0] == "W" * 48  # the long name warns, so it comes first
    assert sorted(names[1:]) == ["Front Desk iPhone", "Lab iPad"]
    assert "warning" in page.locator("#fleetSheet .tpl-fleet-count").first.text_content()
    assert "1 with warnings" in page.text_content("#fleetStatus")

    page.locator("#fleetSheet .tpl-fleet-pick").nth(2).click()  # Lab iPad: file order is kept
    page.wait_for_function(
        "document.querySelector('#previewStatus').textContent.startsWith('Rendered')"
        " && document.querySelector('#previewStatus').textContent.includes('custom values')")
    assert page.input_value("#sample-device_name") == "Lab iPad"
    assert page.input_value("#sample-location-building") == "East, Wing"
    assert json.loads(page.input_value("#sampleValues"))["jss_id"] == 3


def load_csv(page, tmp_path):
    csv = tmp_path / "fleet.csv"
    csv.write_text(CSV)
    page.set_input_files("#fleetFile", str(csv))
    page.wait_for_function("document.querySelectorAll('#fleetSheet .tpl-fleet-pick').length === 3")


def shown_names(page):
    return page.locator("#fleetSheet > li:not([hidden]) .tpl-fleet-name").all_text_contents()


def test_the_summary_leads_with_how_many_fit_and_splits_the_rest_by_problem(designer, tmp_path):
    page = designer
    load_csv(page, tmp_path)
    assert page.text_content("#fleetFitCount") == "2"
    assert page.text_content("#fleetFitOf") == "of 3 devices fit with no warnings"
    assert page.get_attribute("#fleetBar", "aria-label") == "2 fit (67%), 1 need attention (33%)"
    assert page.locator("#fleetBar .tpl-fleet-block").all_text_contents() == ["67%", "33%"]

    # Each problem row names its kind in words and counts devices.
    kinds = page.locator("#fleetKinds .tpl-fleet-kind")
    assert kinds.count() >= 1
    assert kinds.first.locator(".tpl-fleet-kind-count").text_content() == "1 device"

    # A problem row filters the sheet; pressing it again shows every device.
    kinds.first.click()
    assert kinds.first.get_attribute("aria-pressed") == "true"
    assert shown_names(page) == ["W" * 48]
    kinds.first.click()
    assert len(shown_names(page)) == 3

    page.click("#fleetFilters [data-fleet-filter=fit]")
    assert sorted(shown_names(page)) == ["Front Desk iPhone", "Lab iPad"]
    page.click("#fleetFilters [data-fleet-filter=all]")
    assert len(shown_names(page)) == 3

    facts = page.locator("#fleetFacts .tpl-fleet-fact")
    assert facts.nth(0).locator("dt").text_content() == "Longest name"
    assert facts.nth(0).locator(".tpl-fleet-fact-value").text_content() == "W" * 48
    assert "48 characters" in facts.nth(0).text_content()
    assert facts.nth(1).locator("dt").text_content() == "Smallest text"
    assert facts.nth(1).locator(".tpl-fleet-fact-value").text_content().endswith(" px")
    assert "layer 1 on " + "W" * 48 in facts.nth(1).text_content()

    # The longest name previews that device.
    facts.nth(0).locator("button").click()
    page.wait_for_function("document.querySelector('#sample-device_name').value.length === 48")


def test_the_summary_says_out_of_date_after_a_template_edit_and_not_after_undo(designer, tmp_path):
    page = designer
    load_csv(page, tmp_path)
    assert page.is_hidden("#fleetStale")

    page.fill("#tplName", "Lobby")  # the name is not drawn
    page.wait_for_function("document.querySelector('#previewStatus').textContent.startsWith('Rendered')")
    assert page.is_hidden("#fleetStale")

    page.click('[aria-label="Delete layer 2"]')
    page.wait_for_selector("#fleetStale:not([hidden])")
    assert "Out of date" in page.text_content("#fleetStale")
    assert "is-stale" in page.get_attribute("#fleetSummary", "class")
    assert "is-stale" in page.get_attribute("#fleetSheet", "class")

    page.click("#undoButton")
    page.wait_for_selector("#fleetStale", state="hidden")

    page.click('[aria-label="Delete layer 2"]')
    page.wait_for_selector("#fleetStale:not([hidden])")
    page.click("#fleetStaleRecheck")
    page.wait_for_selector("#fleetStale", state="hidden")
    assert "is-stale" not in page.get_attribute("#fleetSummary", "class")


def test_the_summary_fits_a_phone(page, tmp_path):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    load_csv(page, tmp_path)
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    box = page.locator("#fleetSummary").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 390
    row = page.locator("#fleetKinds .tpl-fleet-kind").first.bounding_box()
    assert row["height"] >= 44


def test_the_summary_names_the_layer_behind_the_warnings(designer, tmp_path):
    page = designer
    load_csv(page, tmp_path)
    rows = page.locator("#fleetLayers .tpl-fleet-kind")
    assert page.is_visible("#fleetLayersHeading")
    first = rows.first
    assert first.locator(".tpl-fleet-kind-name").text_content().strip().startswith("1. Text:")
    assert "Mostly: " in first.locator(".tpl-fleet-kind-detail").text_content()
    assert first.locator(".tpl-fleet-kind-count").text_content() == "1 device"

    # Pick the QR layer first, so selecting layer 1 from the summary shows.
    page.locator("#layerList .layer-select").nth(1).click()
    first.click()
    assert first.get_attribute("aria-pressed") == "true"
    assert shown_names(page) == ["W" * 48]
    assert page.get_attribute("#layerList .layer-select >> nth=0", "aria-pressed") == "true"
    assert "Layer 1" in page.get_attribute("#fleetSheet", "aria-label")
    first.click()
    assert len(shown_names(page)) == 3


def test_a_recheck_shows_the_change_since_the_last_check(designer, tmp_path):
    page = designer
    load_csv(page, tmp_path)
    assert page.is_hidden("#fleetDelta")  # nothing to compare with yet
    kind = page.locator("#fleetKinds .tpl-fleet-kind").first
    kind_name = kind.locator(".tpl-fleet-kind-name").text_content()

    page.click('[aria-label="Delete layer 1"]')  # the device name layer, the one that warned
    page.wait_for_selector("#fleetStale:not([hidden])")
    page.click("#fleetStaleRecheck")
    page.wait_for_selector("#fleetDelta:not([hidden])")
    delta = page.text_content("#fleetDelta")
    assert delta == "▼ 1 fewer need attention"
    assert "is-better" in page.get_attribute("#fleetDelta .tpl-fleet-change", "class")

    # The fixed problem stays as a row at 0 with its change, and cannot filter.
    gone = page.locator("#fleetKinds .tpl-fleet-kind", has_text=kind_name.strip())
    assert gone.locator(".tpl-fleet-kind-count").text_content() == "0 devices▼ 1 fewer"
    assert gone.is_disabled()

    page.click("#undoButton")
    page.wait_for_selector("#fleetStale:not([hidden])")
    page.click("#fleetStaleRecheck")
    page.wait_for_function("document.querySelector('#fleetDelta').textContent.startsWith('▲')")
    assert page.text_content("#fleetDelta") == "▲ 1 more need attention"
    assert "is-worse" in page.get_attribute("#fleetDelta .tpl-fleet-change", "class")

    load_csv(page, tmp_path)  # a new list starts over
    page.wait_for_function("document.querySelector('#fleetStatus').textContent.startsWith('Checked')")
    assert page.is_hidden("#fleetDelta")


def test_a_long_list_checks_in_chunks_and_stop_keeps_what_was_checked(designer, tmp_path):
    page = designer
    csv = tmp_path / "fleet.csv"
    csv.write_text("device_name\r\n" + "".join(f"iPad {n}\r\n" for n in range(1, 26)))
    held = []

    def route(r):
        body = json.loads(r.request.post_data)
        if body.get("first", 1) == 1:
            r.continue_()
        else:
            held.append(r)  # later chunks never answer until Stop

    page.route("**/api/template/preview-batch", route)
    page.set_input_files("#fleetFile", str(csv))
    page.wait_for_function("document.querySelector('#fleetProgressText').textContent.startsWith('Checked 10 ')")
    assert page.text_content("#fleetProgressText") == "Checked 10 of 25 devices"
    assert page.get_attribute("#fleetProgressBar", "aria-valuenow") == "10"
    assert page.locator("#fleetSheet .tpl-fleet-pick").count() == 10  # the sheet fills in as it goes
    assert page.text_content("#fleetFitOf").startswith("of 10 devices")  # and so does the summary
    assert page.is_disabled("#fleetRecheck")

    page.click("#fleetStop")
    page.wait_for_selector("#fleetProgress", state="hidden")
    assert page.text_content("#fleetStatus").startswith("Stopped after 10 of 25 devices")
    assert page.locator("#fleetSheet .tpl-fleet-pick").count() == 10
    assert page.is_enabled("#fleetRecheck")
    assert held and json.loads(held[0].request.post_data)["first"] == 11
    page.unroute_all(behavior="ignoreErrors")


def test_the_device_list_is_remembered_only_when_asked(designer, tmp_path):
    page = designer
    load_csv(page, tmp_path)
    assert page.text_content("#fleetRememberState") == "Off"
    page.reload()
    page.wait_for_selector("#previewImage:not([hidden])")
    assert page.is_hidden("#fleetRemembered")  # Off by default: nothing kept

    load_csv(page, tmp_path)
    page.check("#fleetRemember")
    assert page.text_content("#fleetRememberState") == "On"
    page.reload()
    page.wait_for_selector("#previewImage:not([hidden])")
    assert page.text_content("#fleetRememberedText") == "3 devices from fleet.csv, remembered in this browser."
    assert page.is_checked("#fleetRemember")
    page.click("#fleetRememberedCheck")
    page.wait_for_function("document.querySelectorAll('#fleetSheet .tpl-fleet-pick').length === 3")
    assert page.is_hidden("#fleetRemembered")

    page.reload()
    page.wait_for_selector("#fleetRemembered:not([hidden])")
    page.click("#fleetForget")
    assert page.text_content("#fleetStatus").startswith("Forgotten")
    assert page.evaluate("localStorage.getItem('ewok-fleet')") is None
    page.reload()
    page.wait_for_selector("#previewImage:not([hidden])")
    assert page.is_hidden("#fleetRemembered")
