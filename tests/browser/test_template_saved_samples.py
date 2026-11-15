"""Template designer in a browser: the designer's own sample devices, kept in this browser."""

import json

import pytest

KEY = "ewok-sample-devices"


@pytest.fixture()
def designer(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    return page


def saved_options(page):
    return page.eval_on_selector_all(
        "#samplePreset optgroup[data-saved] option", "els => els.map(e => e.textContent)")


def save_as(page, name):
    page.click("#saveSample")
    assert page.is_visible("#saveSampleName")
    page.fill("#saveSampleName", name)
    page.click("#saveSampleForm button[type=submit]")


def type_my_ipad(page):
    page.fill("#sample-device_name", "Chief's iPad")
    page.fill("#sample-asset_tag", "IT-0001")
    assert page.input_value("#samplePreset") == "custom"


def test_save_names_the_device_and_adds_it_below_the_built_ins(designer):
    page = designer
    assert saved_options(page) == []
    type_my_ipad(page)
    page.click("#saveSample")
    # The name starts as the device name, ready to keep or change.
    assert page.input_value("#saveSampleName") == "Chief's iPad"
    page.fill("#saveSampleName", "My iPad")
    page.press("#saveSampleName", "Enter")

    assert saved_options(page) == ["My iPad"]
    labels = page.eval_on_selector_all("#samplePreset > *", "els => els.map(e => e.label || e.textContent)")
    assert labels[-2:] == ["Saved in this browser", "Custom (edit the values under Sample device)"]
    assert page.input_value("#samplePreset") == "saved-0"
    assert page.inner_text("#savedSampleStatus").startswith('✓ Saved "My iPad".')
    page.wait_for_function(
        "document.querySelector('#previewStatus').textContent.includes('My iPad (Chief')")
    assert page.inner_text("#savedSampleList").count("My iPad") == 1


def test_a_saved_device_survives_a_reload_and_previews_its_values(designer):
    page = designer
    type_my_ipad(page)
    save_as(page, "My iPad")
    page.reload()
    page.wait_for_selector("#previewImage:not([hidden])")
    assert saved_options(page) == ["My iPad"]
    assert page.input_value("#sample-device_name") == "Front Desk iPhone"  # built-in first, as before
    with page.expect_request(lambda r: r.url.endswith("/api/template/preview")) as info:
        page.select_option("#samplePreset", "saved-0")
    assert info.value.post_data_json["values"]["asset_tag"] == "IT-0001"
    assert page.input_value("#sample-device_name") == "Chief's iPad"


def test_saving_the_same_name_again_updates_it(designer):
    page = designer
    type_my_ipad(page)
    save_as(page, "My iPad")
    page.fill("#sample-asset_tag", "IT-0002")
    page.click("#saveSample")
    assert page.input_value("#saveSampleName") == "Chief's iPad"
    page.fill("#saveSampleName", "My iPad")
    page.click("#saveSampleForm button[type=submit]")
    assert saved_options(page) == ["My iPad"]
    assert page.inner_text("#savedSampleStatus").startswith('✓ Updated "My iPad".')
    stored = json.loads(page.evaluate(f"localStorage.getItem('{KEY}')"))
    assert stored[0]["values"]["asset_tag"] == "IT-0002"


def test_an_empty_name_is_not_saved(designer):
    page = designer
    save_as(page, "   ")
    assert saved_options(page) == []
    assert page.inner_text("#savedSampleStatus") == "Not saved: give the device a name."
    page.click("#saveSampleCancel")
    assert not page.is_visible("#saveSampleForm")
    assert page.is_visible("#saveSample")


def test_rename_and_remove_with_undo(designer):
    page = designer
    type_my_ipad(page)
    save_as(page, "My iPad")
    page.fill("#sample-device_name", "Lobby Kiosk With A Very Long Name")
    save_as(page, "Kiosk")
    assert saved_options(page) == ["My iPad", "Kiosk"]

    page.click('[aria-label="Rename My iPad"]')
    page.fill('[aria-label="New name for My iPad"]', "Test iPad")
    page.press('[aria-label="New name for My iPad"]', "Enter")
    assert saved_options(page) == ["Test iPad", "Kiosk"]
    assert page.inner_text("#savedSampleStatus") == 'Renamed "My iPad" to "Test iPad".'
    assert page.input_value("#samplePreset") == "saved-1"  # the pick stays on Kiosk

    page.click('[aria-label="Remove Test iPad"]')
    assert saved_options(page) == ["Kiosk"]
    assert page.input_value("#samplePreset") == "saved-0"
    assert page.inner_text("#savedSampleStatus").startswith('Removed "Test iPad" from this browser.')
    page.click('[aria-label="Undo removing Test iPad"]')
    assert saved_options(page) == ["Test iPad", "Kiosk"]
    assert page.input_value("#samplePreset") == "saved-1"

    page.click('[aria-label="Remove Kiosk"]')
    page.click('[aria-label="Remove Test iPad"]')
    assert saved_options(page) == []
    assert page.locator("#samplePreset optgroup").count() == 0
    assert page.input_value("#samplePreset") == "custom"
    assert page.evaluate(f"localStorage.getItem('{KEY}')") is None
    page.reload()
    page.wait_for_selector("#previewImage:not([hidden])")
    assert saved_options(page) == []


def test_saved_values_stay_out_of_the_draft_and_the_download(designer):
    page = designer
    type_my_ipad(page)
    save_as(page, "My iPad")
    draft = page.evaluate("localStorage.getItem('ewok-template-draft')") or ""
    assert "IT-0001" not in draft and "My iPad" not in draft
    with page.expect_download() as info:
        page.click("#downloadPackage")
    package = open(info.value.path()).read()
    assert "IT-0001" not in package and "My iPad" not in package


def test_blocked_storage_says_not_saved(designer):
    page = designer
    page.evaluate("() => { Storage.prototype.setItem = () => { throw new Error('blocked'); }; }")
    save_as(page, "My iPad")
    assert saved_options(page) == []
    assert page.inner_text("#savedSampleStatus") == (
        "Not saved: this browser does not allow EWOK to keep it.")


def test_the_saved_list_fits_a_phone(designer):
    page = designer
    page.set_viewport_size({"width": 390, "height": 844})
    page.fill("#sample-device_name", "Lobby Kiosk With A Very Long Device Name For Testing")
    save_as(page, "Lobby kiosk with a long name")
    row = page.locator("#savedSampleList li").bounding_box()
    assert row["x"] >= 0 and row["x"] + row["width"] <= 390
    assert page.evaluate("document.documentElement.scrollWidth") <= 390
