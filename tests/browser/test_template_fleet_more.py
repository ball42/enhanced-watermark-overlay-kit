"""Template designer in a browser: name headroom, buildings, the report and checking after each edit."""

import csv
import io

from tests.browser.test_template_fleet import designer, load_csv, shown_names  # noqa: F401


def test_the_name_strip_says_how_long_a_name_can_be(designer, tmp_path):  # noqa: F811
    page = designer
    load_csv(page, tmp_path)
    assert page.is_visible("#fleetNames")
    # Front Desk iPhone (17) fits, 48 Ws shrink: the break point sits between them.
    say = page.text_content("#fleetNamesSay")
    assert "Names fit up to 17 characters." in say
    assert "⚠ 1 device is longer." in say
    assert page.locator("#fleetStrip .tpl-fleet-mark").count() == 3
    shrank = page.locator("#fleetStrip .tpl-fleet-mark.is-shrank")
    assert shrank.count() == 1
    assert "48 characters, ⚠ shrinks or is cut off" in shrank.get_attribute("aria-label")
    assert "fits up to 17" in page.text_content("#fleetStrip .tpl-fleet-break")

    # Marks are read with the arrow keys, shortest first, and a mark previews its device.
    marks = page.locator("#fleetStrip .tpl-fleet-mark")
    marks.first.focus()
    assert "Lab iPad" in marks.first.get_attribute("aria-label")
    page.keyboard.press("End")
    assert page.evaluate("document.activeElement.classList.contains('is-shrank')")
    page.keyboard.press("Enter")
    page.wait_for_function("document.querySelector('#sample-device_name').value.length === 48")
    assert shrank.get_attribute("aria-current") == "true"


def test_the_name_strip_fits_a_phone(page, tmp_path):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    load_csv(page, tmp_path)
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
    strip = page.locator("#fleetStrip").bounding_box()
    assert strip["x"] >= 0 and strip["x"] + strip["width"] <= 390
    for box in [m.bounding_box() for m in page.locator("#fleetStrip .tpl-fleet-mark").all()]:
        assert box["x"] >= 0 and box["x"] + box["width"] <= 390


def test_by_building_puts_the_worst_site_first_and_filters(designer, tmp_path):  # noqa: F811
    page = designer
    load_csv(page, tmp_path)
    assert page.is_visible("#fleetBuildingsHeading")
    rows = page.locator("#fleetBuildings .tpl-fleet-building")
    assert rows.count() == 3
    first = rows.first
    assert "South" in first.locator(".tpl-fleet-kind-name").text_content()
    assert first.locator(".tpl-fleet-kind-count").text_content() == "⚠ 1 of 1 need attention"
    assert rows.nth(1).locator(".tpl-fleet-kind-count").text_content() == "✓ all fit"
    first.click()
    assert first.get_attribute("aria-pressed") == "true"
    assert shown_names(page) == ["W" * 48]
    assert page.get_attribute("#fleetSheet", "aria-label") == "South: 1 device"
    rows.nth(2).click()
    assert len(shown_names(page)) == 1
    rows.nth(2).click()
    assert len(shown_names(page)) == 3


def test_no_building_column_means_no_building_list(designer, tmp_path):  # noqa: F811
    page = designer
    path = tmp_path / "plain.csv"
    path.write_text("device_name\r\nA\r\nB\r\n")
    page.set_input_files("#fleetFile", str(path))
    page.wait_for_function("document.querySelectorAll('#fleetSheet .tpl-fleet-pick').length === 2")
    assert page.is_hidden("#fleetBuildingsHeading")
    assert page.locator("#fleetBuildings li").count() == 0
    assert "Every name fits." in page.text_content("#fleetNamesSay")


def test_the_report_downloads_every_device_in_file_order(designer, tmp_path):  # noqa: F811
    page = designer
    path = tmp_path / "Lobby fleet.csv"
    path.write_text("device_name,jss_id,location.building\r\n"
                    "Front Desk iPhone,1,North\r\n" + "W" * 48 + ",2,South\r\n=HYPERLINK(1),3,\r\n")
    page.fill("#tplName", "Lobby iPads")
    page.set_input_files("#fleetFile", str(path))
    page.wait_for_function("document.querySelectorAll('#fleetSheet .tpl-fleet-pick').length === 3"
                           " && document.querySelector('#fleetProgress').hidden")
    with page.expect_download() as info:
        page.click("#fleetReport")
    download = info.value
    assert download.suggested_filename == "lobby-ipads-lobby-fleet-report.csv"
    rows = list(csv.reader(io.StringIO(open(download.path(), encoding="utf-8").read())))
    assert rows[0] == ["row", "device_name", "building", "result", "problems", "warnings"]
    assert [r[0] for r in rows[1:]] == ["2", "3", "4"]  # the CSV's own line numbers
    assert rows[1][1:4] == ["Front Desk iPhone", "North", "Fit"]
    assert rows[2][1:4] == ["W" * 48, "South", "Needs attention"]
    assert rows[2][4] and rows[2][5]  # the problem names and the warnings
    assert rows[3][1] == "'=HYPERLINK(1)"  # never runs as a formula
    assert "Saved lobby-ipads-lobby-fleet-report.csv: 3 devices" in page.text_content("#fleetStatus")


def test_check_after_each_edit_rechecks_once_after_the_edits_stop(designer, tmp_path):  # noqa: F811
    page = designer
    load_csv(page, tmp_path)
    assert page.is_visible("#fleetAutoRow")
    assert page.text_content("#fleetAutoState") == "Off"
    checks = []
    page.on("request", lambda r: checks.append(r) if r.url.endswith("/preview-batch") else None)

    # Off: an edit only marks the results out of date.
    page.click('[aria-label="Delete layer 2"]')
    page.wait_for_selector("#fleetStale:not([hidden])")
    page.wait_for_timeout(2500)
    assert checks == []
    page.click("#undoButton")
    page.wait_for_selector("#fleetStale", state="hidden")

    page.click("#fleetAuto")
    assert page.text_content("#fleetAutoState") == "On"
    page.click('[aria-label="Delete layer 2"]')
    page.wait_for_selector("#fleetStale", state="hidden", timeout=30000)
    page.wait_for_function("document.querySelector('#fleetProgress').hidden")
    page.wait_for_timeout(2500)  # nothing else runs once the template is checked
    assert len(checks) == 1
    assert "No change since the last check" in page.text_content("#fleetDelta")
