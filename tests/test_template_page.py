"""Template mode T2: the editor page and its navigation."""


def test_template_page_renders(client):
    resp = client.get("/template")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="templateEditor"' in body
    assert "/static/js/template.js" in body
    # Brander's variables are offered for insertion.
    for name in ("device_name", "serial_number", "asset_tag", "jss_id", "location.building"):
        assert f'value="{name}"' in body
    # Canvas presets, including the square iPad canvas that survives rotation.
    assert "2732" in body and "1290" in body


def test_photo_and_template_pages_link_to_each_other(client):
    assert 'href="/template"' in client.get("/").get_data(as_text=True)
    assert 'href="/"' in client.get("/template").get_data(as_text=True)


def test_editor_script_and_styles_are_served(client):
    assert client.get("/static/js/template.js").status_code == 200
    assert client.get("/static/css/template.css").status_code == 200


def test_preview_has_a_box_overlay_with_keyboard_help(client):
    """T3: boxes are drawn over the preview; the keyboard alternative to
    dragging is described next to it and linked from the overlay."""
    body = client.get("/template").get_data(as_text=True)
    assert 'id="overlay"' in body and 'aria-describedby="boxHelp"' in body
    assert "arrow keys move it" in body and "Alt with arrow keys resizes it" in body
    assert "tpl-guide-v" in body and "tpl-guide-h" in body


def test_sample_device_presets_are_offered(client):
    """T4: preset sample devices, including one with no asset tag."""
    import json
    import re

    body = client.get("/template").get_data(as_text=True)
    for label in ("iPhone", "iPad", "No asset tag", "Custom"):
        assert label in body
    data = re.search(r'<script type="application/json" id="sampleDevices">(.*?)</script>', body, re.S)
    presets = json.loads(data.group(1))
    assert {p["values"].get("asset_tag", "") for p in presets} >= {""}
    for preset in presets:
        assert set(preset["values"]) <= {"device_name", "serial_number", "asset_tag", "jss_id", "location"}


def test_stress_toggle_is_on_the_page(client):
    body = client.get("/template").get_data(as_text=True)
    assert 'id="stressToggle"' in body
    assert 'id="stressRenders"' in body


def test_open_and_bundle_download_are_on_the_page(client):
    body = client.get("/template").get_data(as_text=True)
    assert 'id="openTemplate"' in body and 'accept=".json,.zip' in body
    assert 'id="downloadBundle"' in body


def test_device_profiles_and_guides_are_on_the_page(client):
    import json
    import re

    body = client.get("/template").get_data(as_text=True)
    data = re.search(r'<script type="application/json" id="deviceProfiles">(.*?)</script>', body, re.S)
    ids = {p["id"] for p in json.loads(data.group(1))}
    assert {"iphone-6.7", "ipad-12.9"} <= ids
    for element in ('id="guideDevice"', 'id="guideOrientation"', 'id="guideScreen"', 'id="deviceGrid"'):
        assert element in body


def test_roles_editor_is_on_the_page(client):
    body = client.get("/template").get_data(as_text=True)
    for element in ('id="rolesOn"', 'id="roleAttribute"', 'id="variantList"', 'id="addVariant"', 'id="previewRole"'):
        assert element in body
