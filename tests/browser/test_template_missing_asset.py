"""Template designer in a browser: a draft whose assets have gone from the
library says so, still renders the rest, and offers Upload and Remove."""

import io
import json
import os

from PIL import Image

import config


def png(color=(200, 30, 30)):
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), color).save(buf, "PNG")
    return buf.getvalue()


def uses_t_and_logo():
    return {
        "schema_version": 1, "name": "Gone", "canvas": {"width": 1290, "height": 2796},
        "background": {"asset": "t"},
        "layers": [
            {"type": "text", "text": "{{device_name}}", "box": {"x": 0.1, "y": 0.5, "w": 0.8, "h": 0.05},
             "size": 0.028, "color": "#FFFFFF", "align": "center"},
            {"type": "qr", "data": "jamf-device:{{jss_id}}", "box": {"x": 0.35, "y": 0.62, "w": 0.3, "h": 0.14}},
            {"type": "image", "asset": "t", "box": {"x": 0.4, "y": 0.1, "w": 0.2, "h": 0.1}},
            {"type": "image", "asset": "logo", "box": {"x": 0.4, "y": 0.8, "w": 0.2, "h": 0.1}},
        ],
    }


def open_with_gone_assets(page, template):
    """Upload t and logo, keep a draft that uses them, then delete their
    files (a wiped folder, a new machine) and open the designer."""
    for asset_id in ("t", "logo"):
        resp = page.request.post("/api/template/assets", multipart={
            "id": asset_id, "file": {"name": f"{asset_id}.png", "mimeType": "image/png", "buffer": png()}})
        assert resp.ok
    for name in os.listdir(config.TEMPLATE_ASSETS_FOLDER):
        os.remove(os.path.join(config.TEMPLATE_ASSETS_FOLDER, name))
    page.add_init_script(
        "if (!sessionStorage.getItem('seeded')) {"
        f" localStorage.setItem('ewok-template-draft', {json.dumps(json.dumps(template))});"
        " sessionStorage.setItem('seeded', '1'); }")
    page.goto("/template")
    page.wait_for_selector("#missingAssets:not([hidden])")
    rendered(page)


def rendered(page):
    page.wait_for_function("document.querySelector('#previewStatus').textContent.startsWith('Rendered')")
    assert page.is_visible("#previewImage")


def test_a_draft_with_missing_assets_says_so_and_still_renders(page):
    open_with_gone_assets(page, uses_t_and_logo())
    bar = page.inner_text(".tpl-actionbar")
    assert "Restored your last draft." in bar
    assert "2 assets are missing: t, logo" in bar
    # The rest of the template rendered, with no warning about the gone assets.
    assert "not found" not in page.inner_text("#warningList")
    # Every place that uses a missing asset says so in words.
    rows = page.locator("#layerList .layer-select").all_inner_texts()
    assert rows[2] == "3. Image: t (missing)"
    assert rows[3] == "4. Image: logo (missing)"
    assert page.eval_on_selector("#bgAsset", "s => s.selectedOptions[0].textContent") == "t (missing)"
    assert "the background and layer 3" in page.inner_text("#missingAssets")
    for asset_id in ("t", "logo"):
        assert page.locator(f'[aria-label="Upload {asset_id}"]').count() == 1
        assert page.locator(f'[aria-label="Remove {asset_id} from the template"]').count() == 1


def test_remove_from_template_drops_its_uses_and_undo_brings_them_back(page):
    open_with_gone_assets(page, uses_t_and_logo())
    page.click('[aria-label="Remove t from the template"]')
    page.wait_for_function("!document.querySelector('#missingAssets').textContent.includes('t:')"
                           " && document.querySelector('#missingAssets').textContent.includes('logo')")
    rows = page.locator("#layerList .layer-select").all_inner_texts()
    assert len(rows) == 3 and rows[2] == "3. Image: logo (missing)"
    assert page.is_checked('input[name="bgKind"][value="color"]')
    assert "1 asset is missing: logo" in page.inner_text(".tpl-actionbar")
    assert "Removed t from the template" in page.inner_text("#ioStatus")
    rendered(page)
    page.click("#undoButton")
    page.wait_for_function("document.querySelector('#missingAssets').textContent.includes('2 assets')")
    assert len(page.locator("#layerList .layer-select").all_inner_texts()) == 4


def test_removing_every_missing_asset_clears_the_message(page):
    open_with_gone_assets(page, uses_t_and_logo())
    page.click('[aria-label="Remove t from the template"]')
    page.click('[aria-label="Remove logo from the template"]')
    page.wait_for_selector("#missingAssets", state="hidden")
    rendered(page)


def test_upload_puts_the_asset_back_under_its_own_id(page):
    open_with_gone_assets(page, uses_t_and_logo())
    # Any file name: the upload is stored as t, the id the template uses.
    page.set_input_files('[aria-label="Upload t"]', files=[
        {"name": "Holiday Photo.png", "mimeType": "image/png", "buffer": png((10, 120, 200))}])
    page.wait_for_function("!document.querySelector('#missingAssets').textContent.includes('t:')")
    ids = [a["id"] for a in page.request.get("/api/template/assets").json()["assets"]]
    assert ids == ["t"]
    assert page.eval_on_selector("#bgAsset", "s => s.selectedOptions[0].textContent") == "t"
    assert page.locator("#layerList .layer-select").nth(2).inner_text() == "3. Image: t"
    assert "Uploaded t" in page.inner_text("#ioStatus")
    rendered(page)


def test_an_asset_deleted_while_open_is_flagged_and_left_out(page):
    page.request.post("/api/template/assets", multipart={
        "id": "t", "file": {"name": "t.png", "mimeType": "image/png", "buffer": png()}})
    template = uses_t_and_logo()
    template["layers"].pop()
    page.add_init_script(
        f"localStorage.setItem('ewok-template-draft', {json.dumps(json.dumps(template))});")
    page.goto("/template")
    rendered(page)
    assert page.is_hidden("#missingAssets")
    # Another tab deletes t; the next render finds it gone.
    os.remove(os.path.join(config.TEMPLATE_ASSETS_FOLDER, "t.png"))
    page.fill('[data-box="x"]', "0.05")
    page.wait_for_selector("#missingAssets:not([hidden])")
    assert "1 asset is missing: t" in page.inner_text(".tpl-actionbar")
    rendered(page)


def test_opening_a_template_whose_assets_are_not_in_the_library_says_so(page):
    template = uses_t_and_logo()
    template["background"] = {"color": "#0B2545"}
    template["layers"] = template["layers"][:2]
    template["roles"] = {"variants": {"reception": {"background": {"asset": "logo"}}}, "empty": {}, "default": {}}
    page.goto("/template")
    rendered(page)
    page.set_input_files("#openTemplate", files=[
        {"name": "lobby.json", "mimeType": "application/json", "buffer": json.dumps(template).encode()}])
    page.wait_for_selector("#missingAssets:not([hidden])")
    assert "Opened lobby.json." in page.inner_text("#ioStatus")
    assert "1 asset is missing: logo" in page.inner_text(".tpl-actionbar")
    assert "the reception role background" in page.inner_text("#missingAssets")
    rendered(page)
    page.click('[aria-label="Remove logo from the template"]')
    page.wait_for_selector("#missingAssets", state="hidden")
    rendered(page)


def test_on_a_phone_the_bar_with_the_warning_scrolls_away(page):
    page.set_viewport_size({"width": 390, "height": 844})
    open_with_gone_assets(page, uses_t_and_logo())
    position = "e => getComputedStyle(e).position"
    assert page.eval_on_selector(".tpl-actionbar", position) == "static"
    assert page.evaluate("document.documentElement.scrollWidth") == 390
    page.click('[aria-label="Remove t from the template"]')
    page.click('[aria-label="Remove logo from the template"]')
    page.wait_for_selector("#missingAssets", state="hidden")
    assert page.eval_on_selector(".tpl-actionbar", position) == "sticky"
