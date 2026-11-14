"""Template designer in a browser: "Fit the longest name" sizes the name layer
so the names that shrank fit, says what changed, and can be undone."""

import pytest

CSV = ("device_name,asset_tag\r\n"
       "Front Desk iPhone,HR-1\r\n"
       + "W" * 30 + ",HR-2\r\n"
       + "W" * 32 + ",HR-3\r\n"
       "Lab iPad,HR-4\r\n")
SHRANK = "#fleetStrip .tpl-fleet-mark.is-shrank"


@pytest.fixture()
def checked(page, tmp_path):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    csv = tmp_path / "fleet.csv"
    csv.write_text(CSV)
    page.set_input_files("#fleetFile", str(csv))
    page.wait_for_function("document.querySelectorAll('#fleetSheet .tpl-fleet-pick').length === 4"
                           " && document.querySelector('#fleetRecheck').disabled === false")
    return page


def wait_checked(page):
    page.wait_for_function("document.querySelector('#fleetStatus').textContent.includes('Checked 4 devices')"
                           " && document.querySelector('#fleetRecheck').disabled === false")


def test_fit_the_longest_name_leaves_no_device_shrinking(checked):
    page = checked
    assert page.locator(SHRANK).count() == 2
    assert page.is_visible("#fleetFitButton")
    page.click("#fleetFitButton")
    page.wait_for_function("document.querySelector('#fleetFitSay').textContent.includes('Fitted')")
    say = page.text_content("#fleetFitSay")
    assert "Layer 1 size 0.028 → 0.0" in say
    new = float(say.split("→ ")[1][:5])
    assert new < 0.028
    page.wait_for_function("!document.querySelector('#fleetFitSay').textContent.includes('Checking again')")
    wait_checked(page)
    assert page.locator(SHRANK).count() == 0
    assert "Every name fits." in page.text_content("#fleetNamesSay")
    assert page.is_hidden("#fleetFitButton")  # nothing left to fit; the note and Undo stay
    assert page.input_value("#propSize") == str(new)

    page.click("#fleetFitSay button:has-text('Undo')")
    page.wait_for_function("document.querySelector('#fleetFitSay').textContent.startsWith('Undone')")
    assert page.input_value("#propSize") == "0.028"
    page.wait_for_function(f"document.querySelectorAll('{SHRANK}').length === 2")


def test_names_too_long_to_read_say_so_and_change_nothing(page, tmp_path):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    csv = tmp_path / "fleet.csv"
    csv.write_text("device_name\r\nLab iPad\r\n" + "W" * 60 + "\r\n")
    page.set_input_files("#fleetFile", str(csv))
    page.wait_for_function("document.querySelector('#fleetStatus').textContent.includes('Checked 2 devices')")
    page.click("#fleetFitButton")
    page.wait_for_function("document.querySelector('#fleetFitSay').textContent.includes('readable')")
    assert "Make the box wider" in page.text_content("#fleetFitSay")
    assert page.input_value("#propSize") == "0.028"
