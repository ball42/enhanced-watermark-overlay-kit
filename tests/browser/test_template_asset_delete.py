"""Template designer in a browser: deleting an asset the template uses asks first."""

import io
import json

from PIL import Image


def png():
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


def uses_logo():
    return {
        "schema_version": 1, "name": "Logo", "canvas": {"width": 1290, "height": 2796},
        "background": {"asset": "logo"},
        "layers": [
            {"type": "text", "text": "{{device_name}}", "box": {"x": 0.1, "y": 0.5, "w": 0.8, "h": 0.05},
             "size": 0.028, "color": "#FFFFFF", "align": "center"},
            {"type": "qr", "data": "jamf-device:{{jss_id}}", "box": {"x": 0.35, "y": 0.62, "w": 0.3, "h": 0.14}},
            {"type": "image", "asset": "logo", "box": {"x": 0.4, "y": 0.1, "w": 0.2, "h": 0.1}},
        ],
    }


def open_designer(page, template):
    for asset_id in ("logo", "spare"):
        resp = page.request.post("/api/template/assets", multipart={
            "id": asset_id, "file": {"name": f"{asset_id}.png", "mimeType": "image/png", "buffer": png()}})
        assert resp.ok
    page.add_init_script(
        f"localStorage.setItem('ewok-template-draft', {json.dumps(json.dumps(template))});")
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.click("#assetsSection > summary")  # the Assets section starts collapsed
    page.wait_for_selector('[aria-label="Delete asset logo"]')


def asset_ids(page):
    return [a["id"] for a in page.request.get("/api/template/assets").json()["assets"]]


def test_deleting_a_used_asset_names_where_it_is_used_and_cancel_keeps_it(page):
    open_designer(page, uses_logo())
    messages = []
    page.once("dialog", lambda d: (messages.append(d.message), d.dismiss()))
    page.click('[aria-label="Delete asset logo"]')
    assert messages == ["logo is used by the background and layer 3. Delete it anyway?"]
    assert "logo" in asset_ids(page)
    assert page.locator('[aria-label="Delete asset logo"]').count() == 1


def test_confirming_deletes_the_used_asset(page):
    open_designer(page, uses_logo())
    page.once("dialog", lambda d: d.accept())
    page.click('[aria-label="Delete asset logo"]')
    page.wait_for_selector('[aria-label="Delete asset logo"]', state="detached")
    assert "logo" not in asset_ids(page)


def test_a_role_background_counts_as_a_use(page):
    template = uses_logo()
    template["background"] = {"color": "#0B2545"}
    template["layers"].pop()
    template["roles"] = {"variants": {"reception": {"background": {"asset": "logo"}}}, "empty": {}, "default": {}}
    open_designer(page, template)
    messages = []
    page.once("dialog", lambda d: (messages.append(d.message), d.dismiss()))
    page.click('[aria-label="Delete asset logo"]')
    assert messages == ["logo is used by the reception role background. Delete it anyway?"]


def test_deleting_an_unused_asset_needs_no_confirm(page):
    open_designer(page, uses_logo())
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.click('[aria-label="Delete asset spare"]')
    page.wait_for_selector('[aria-label="Delete asset spare"]', state="detached")
    assert dialogs == []
    assert asset_ids(page) == ["logo"]
