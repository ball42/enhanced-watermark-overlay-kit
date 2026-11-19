"""The preview's description: what the wallpaper says, for its alt text."""

TEMPLATE = {
    "schema_version": 1,
    "canvas": {"width": 300, "height": 600},
    "background": {"color": "#0B2545"},
    "layers": [
        {"type": "text", "text": "{{device_name}}", "box": {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.1},
         "size": 0.04, "color": "#FFFFFF"},
        {"type": "panel", "box": {"x": 0.1, "y": 0.3, "w": 0.8, "h": 0.1}, "color": "#000000"},
        {"type": "text", "text": "Tag {{asset_tag}}", "hide_if_empty": True,
         "box": {"x": 0.1, "y": 0.5, "w": 0.8, "h": 0.1}, "size": 0.04, "color": "#FFFFFF"},
        {"type": "qr", "data": "jamf-device:{{jss_id}}", "box": {"x": 0.3, "y": 0.7, "w": 0.4, "h": 0.2}},
    ],
}


def describe(client, values, stress=False):
    resp = client.post("/api/template/preview", json={"template": TEMPLATE, "values": values, "stress": stress})
    assert resp.status_code == 200, resp.get_json()
    return [r["description"] for r in resp.get_json()["renders"]]


def test_names_the_canvas_and_each_text_and_qr_value(client):
    [text] = describe(client, {"device_name": "Front Desk iPhone", "asset_tag": "A-7", "jss_id": 42})
    assert text == "300×600 wallpaper: text 'Front Desk iPhone', text 'Tag A-7', QR jamf-device:42"


def test_leaves_out_a_layer_hidden_for_an_empty_value(client):
    [text] = describe(client, {"device_name": "Ward 3 iPad", "jss_id": 7})
    assert text == "300×600 wallpaper: text 'Ward 3 iPad', QR jamf-device:7"


def test_stress_renders_describe_their_own_values(client):
    sample, long, empty = describe(client, {"device_name": "iPad", "jss_id": 1}, stress=True)
    assert "'iPad'" in sample and "'iPad'" not in long
    assert empty == "300×600 wallpaper: QR jamf-device:"
