"""Template designer in a browser: low contrast carries its fix, the JAWA
download has a preflight, dragging snaps with a labelled guide, and each
package download is listed with the sha256 JAWA's store shows."""

import hashlib
import json

LOW = "#2a3f66"  # dark blue text on the navy background: about 1.5:1


def set_color(page, value, selector="#propColor"):
    page.eval_on_selector(selector, """(e, v) => {
        e.value = v;
        e.dispatchEvent(new Event('input', { bubbles: true }));
        e.dispatchEvent(new Event('change', { bubbles: true }));
    }""", value)


def low_contrast(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    set_color(page, LOW)
    page.wait_for_function("document.querySelector('#warningList').textContent.includes('low contrast')")
    return page


def test_use_white_text_fixes_the_warning_and_undo_takes_it_back(page):
    low_contrast(page)
    item = page.locator("#warningList li", has_text="low contrast")
    assert item.locator("button", has_text="Use white text").count() == 1
    assert item.locator("button", has_text="Add a backdrop").count() == 1
    item.locator("button", has_text="Use white text").click()
    say = page.text_content("#contrastSay")
    assert say.startswith("✓ Contrast 1.") and "→ " in say and "Layer 1 is now white text" in say
    page.wait_for_function("!document.querySelector('#warningList').textContent.includes('low contrast')")
    assert page.input_value("#propColor") == "#ffffff"
    page.click("#contrastSay button:has-text('Undo')")
    assert page.text_content("#contrastSay").startswith("Undone")
    assert page.input_value("#propColor") == LOW
    page.wait_for_function("document.querySelector('#warningList').textContent.includes('low contrast')")


def test_add_a_backdrop_puts_a_panel_just_behind_the_text(page):
    low_contrast(page)
    before = page.locator("#layerList > li").count()
    page.click("#warningList button:has-text('Add a backdrop')")
    page.wait_for_function("document.querySelector('#contrastSay').textContent.includes('Contrast')")
    assert page.locator("#layerList > li").count() == before + 1
    assert page.text_content("#layerList > li:first-child").startswith("1. Panel")
    assert "(now layer 2)" in page.text_content("#contrastSay")
    page.wait_for_function("!document.querySelector('#warningList').textContent.includes('low contrast')")


def test_the_preflight_says_what_is_left_and_ready_when_all_pass(page, tmp_path):
    low_contrast(page)
    page.hover("#downloadPackage")
    page.wait_for_selector("#preflight:not([hidden])")
    lines = page.locator(".tpl-preflight-line").all_text_contents()
    assert lines[0] == "Renders on JAWA's wallrender 0.9"
    assert lines[1] == "Same Pillow as JAWA (13.0)"
    assert lines[2].startswith("Not checked against your devices")
    assert lines[3].startswith("1 contrast warning")
    assert lines[4] == "No assets to include"
    assert page.text_content("#downloadPackage").strip() == "Download for JAWA's template store"
    page.mouse.move(5, 600)
    page.wait_for_selector("#preflight", state="hidden")

    # Fix the contrast and check two devices: every line passes.
    page.click("#warningList button:has-text('Use white text')")
    csv = tmp_path / "fleet.csv"
    csv.write_text("device_name,jss_id\r\nLab iPad,12\r\nFront Desk,13\r\n")
    page.set_input_files("#fleetFile", str(csv))
    page.wait_for_function("document.querySelector('#fleetStatus').textContent.includes('Checked 2 devices')")
    page.wait_for_function("document.querySelector('#downloadPackage').textContent.includes('Ready')")
    assert page.text_content("#downloadPackage").strip() == "Ready: Download for JAWA"
    page.click("#preflightToggle")  # the menu opens without hover, as on a phone
    assert page.get_attribute("#preflightToggle", "aria-expanded") == "true"
    assert "2 of 2 devices fit" in page.locator(".tpl-preflight-line").all_text_contents()
    assert page.text_content("#preflightVerdict") == "✓ Ready to send to JAWA."
    page.keyboard.press("Escape")
    assert page.is_hidden("#preflight")


def test_a_package_download_names_its_sha256_and_is_listed(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.fill("#tplName", "Kiosk wallpaper")
    with page.expect_download() as info:
        page.click("#downloadPackage")
    package = json.loads(open(info.value.path()).read())
    digest = hashlib.sha256((json.dumps(package["template"], indent=2) + "\n").encode()).hexdigest()
    page.wait_for_function("document.querySelector('#ioStatus').textContent.includes('sha256')")
    status = page.text_content("#ioStatus")
    assert status.startswith(f"Downloaded kiosk-wallpaper.brander.json · sha256 {digest[:12]} · ")

    page.reload()
    page.wait_for_selector("#previewImage:not([hidden])")
    page.click("#moreActions summary")
    page.click("#showDownloads")
    row = page.locator("#downloadsList .tpl-download")
    assert row.count() == 1
    assert row.locator(".tpl-download-file").text_content() == "kiosk-wallpaper.brander.json"
    assert row.locator(".tpl-download-sha").text_content() == f"sha256 {digest[:12]}"
    assert row.locator(".tpl-download-sha").get_attribute("title") == digest
    assert row.locator(".tpl-download-thumb img").count() == 1
    page.click("#downloadsClear")
    assert "No packages downloaded" in page.text_content("#downloadsList")
    page.click("#downloadsClose")


def drag_qr_near_text_edge(page, alt=False):
    """Drag the QR box (layer 2) so its left edge is 3 screen px right of
    the name's left edge (layer 1, x 0.1), and report while still dragging."""
    stage = page.locator("#stage").bounding_box()
    frame = page.locator('#overlay .tpl-boxframe[data-index="1"]')
    box = frame.bounding_box()
    sx, sy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    target_left = stage["x"] + 0.1 * stage["width"] + 3
    dx = target_left - box["x"]
    page.mouse.move(sx, sy)
    if alt:
        page.keyboard.down("Alt")
    page.mouse.down()
    page.mouse.move(sx + dx / 2, sy + 40, steps=4)
    page.mouse.move(sx + dx, sy + 40, steps=4)
    guide = page.locator(".tpl-guide-v")
    seen = (guide.is_visible(), guide.text_content())
    page.mouse.up()
    if alt:
        page.keyboard.up("Alt")
    return seen, float(page.input_value('[data-box="x"]'))


def test_dragging_snaps_to_another_layer_with_a_labelled_guide(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    (visible, label), x = drag_qr_near_text_edge(page)
    assert visible and label == "aligns with Layer 1"
    assert x == 0.1
    assert page.is_hidden(".tpl-guide-v")  # gone once dropped


def test_option_drags_without_snapping(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    (visible, _), x = drag_qr_near_text_edge(page, alt=True)
    assert not visible
    assert x != 0.1 and abs(x - 0.1) < 0.03
