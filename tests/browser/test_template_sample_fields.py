"""Template designer in a browser: sample values are labelled fields."""

import json

import pytest


@pytest.fixture()
def designer(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    return page


def json_values(page):
    return json.loads(page.input_value("#sampleValues"))


def test_fields_show_the_preset_values(designer):
    page = designer
    assert page.input_value("#sample-device_name") == "Front Desk iPhone"
    assert page.input_value("#sample-location-building") == "North Campus"
    page.select_option("#samplePreset", "1")
    assert page.input_value("#sample-device_name") == "Ward 3 iPad"


def test_a_long_device_name_typed_in_its_field_warns(designer):
    page = designer
    page.fill("#sample-device_name", "W" * 48)
    page.wait_for_function(
        "/shortened|shrank/.test(document.querySelector('#warningList').textContent)")
    assert page.input_value("#samplePreset") == "custom"
    assert json_values(page)["device_name"] == "W" * 48


def test_empty_clears_the_building_and_the_json_view_follows(designer):
    page = designer
    page.click('[data-empty="location.building"]')
    assert page.input_value("#sample-location-building") == ""
    assert json_values(page)["location"] == {"building": ""}
    page.wait_for_function(
        "document.querySelector('#previewStatus').textContent.startsWith('Rendered')"
        " && document.querySelector('#previewStatus').textContent.includes('custom values')")


def test_person_fields_show_only_when_the_template_opts_in(designer):
    page = designer
    assert not page.is_visible("#sample-user-email")
    page.check("#personFields")
    assert page.is_visible("#sample-user-email")
    assert page.input_value("#sample-user-email") == "jordan.doe@example.org"


def test_bad_json_shows_an_error_and_keeps_the_fields(designer):
    page = designer
    page.click(".tpl-json-values summary")
    page.fill("#sampleValues", '{"device_name": ')
    assert page.is_visible("#sampleError")
    assert page.locator("#sampleError i.fa-circle-exclamation").count() == 1
    assert page.input_value("#sample-device_name") == "Front Desk iPhone"
    page.fill("#sampleValues", '{"device_name": "Lab Mac"}')
    assert not page.is_visible("#sampleError")
    assert page.input_value("#sample-device_name") == "Lab Mac"
