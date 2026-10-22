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
