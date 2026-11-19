"""Low contrast carries its fix, the preview says what the JAWA preflight
needs, and a package download names the sha256 JAWA's store will show."""

import copy
import hashlib
import json

import wallrender

GREY = "#808080"
TEMPLATE = {
    "schema_version": 1,
    "name": "Kiosk wallpaper",
    "canvas": {"width": 1290, "height": 2796},
    "background": {"color": GREY},
    "layers": [
        {"type": "text", "text": "{{device_name}}", "box": {"x": 0.1, "y": 0.5, "w": 0.8, "h": 0.05},
         "size": 0.02, "color": "#999999", "align": "center"},
        {"type": "text", "text": "{{asset_tag}}", "box": {"x": 0.1, "y": 0.6, "w": 0.8, "h": 0.05},
         "size": 0.02, "color": "#FFFFFF", "align": "center"},
    ],
}
VALUES = {"device_name": "Front Desk iPad", "asset_tag": "HR-1"}


def contrast_warnings(template, values, layer=0):
    return [w for w in wallrender.lint(template, values, lambda _id: b"")
            if w.startswith(f"layer {layer}:") and "low contrast" in w]


def preview(client, template=TEMPLATE, values=VALUES):
    resp = client.post("/api/template/preview", json={"template": template, "values": values})
    assert resp.status_code == 200
    return resp.get_json()


def test_a_low_contrast_text_layer_offers_the_text_color_that_passes(client):
    body = preview(client)
    render = body["renders"][0]
    fixes = {f["index"]: f for f in render["contrast"]}
    assert set(fixes) == {0, 1}  # grey on grey, and white on mid grey (3.9:1)
    fix = fixes[0]
    assert fix["ratio"] < 1.5 and fix["needed"] == 4.5
    assert fix["text"]["name"] == "dark" and fix["text"]["ratio"] >= 4.5
    fixed = copy.deepcopy(TEMPLATE)
    fixed["layers"][0]["color"] = fix["text"]["color"]
    assert contrast_warnings(fixed, VALUES) == []
    # The kinds line up with the warnings, one each.
    assert len(render["kinds"]) == len(render["warnings"])
    assert render["kinds"].count("contrast") == 2


def test_the_better_colour_is_offered_and_none_when_neither_passes(client):
    template = copy.deepcopy(TEMPLATE)
    template["background"] = {"color": "#595959"}  # white 7:1, dark about 2.6:1
    assert preview(client, template)["renders"][0]["contrast"][0]["text"]["name"] == "white"
    template["background"] = {"color": "#777777"}  # white 4.48:1, dark about 4.0:1: neither
    fix = preview(client, template)["renders"][0]["contrast"][0]
    assert fix["text"] is None and fix["ratio"] < 4.5
    # A backdrop still gets there.
    body = client.post("/api/template/backdrop",
                       json={"template": template, "values": VALUES, "index": 0}).get_json()
    assert body["panel"] and body["to"] >= 4.5


def test_text_with_enough_contrast_has_no_fix(client):
    template = copy.deepcopy(TEMPLATE)
    template["background"] = {"color": "#0B2545"}
    template["layers"][0]["color"] = "#FFFFFF"
    assert preview(client, template)["renders"][0]["contrast"] == []


def test_a_backdrop_reaches_the_ratio_and_the_warning_goes(client):
    resp = client.post("/api/template/backdrop", json={"template": TEMPLATE, "values": VALUES, "index": 0})
    assert resp.status_code == 200
    body = resp.get_json()
    panel = body["panel"]
    assert panel["type"] == "panel" and 0 < panel["opacity"] <= 1
    assert body["from"] < 4.5 <= body["to"]
    box = TEMPLATE["layers"][0]["box"]
    assert panel["box"]["x"] < box["x"] and panel["box"]["y"] < box["y"]
    assert panel["box"]["x"] + panel["box"]["w"] > box["x"] + box["w"]
    fixed = copy.deepcopy(TEMPLATE)
    fixed["layers"].insert(0, panel)
    assert contrast_warnings(fixed, VALUES, layer=1) == []
    # The lowest opacity that does it: one step less is not enough.
    weaker = copy.deepcopy(fixed)
    weaker["layers"][0]["opacity"] = round(panel["opacity"] - 0.05, 2)
    if weaker["layers"][0]["opacity"] > 0:
        assert contrast_warnings(weaker, VALUES, layer=1)


def test_a_backdrop_for_text_that_already_passes_is_none(client):
    template = copy.deepcopy(TEMPLATE)
    template["layers"][0]["color"] = "#000000"
    body = client.post("/api/template/backdrop",
                       json={"template": template, "values": VALUES, "index": 0}).get_json()
    assert body["panel"] is None and body["to"] >= 4.5


def test_backdrop_refuses_what_is_not_a_text_layer(client):
    template = copy.deepcopy(TEMPLATE)
    template["layers"].append({"type": "panel", "box": {"x": 0, "y": 0, "w": 1, "h": 1}})
    for index in (2, 9, -1, "0"):
        resp = client.post("/api/template/backdrop",
                           json={"template": template, "values": VALUES, "index": index})
        assert resp.status_code == 400
    empty = client.post("/api/template/backdrop", json={"template": TEMPLATE, "values": {}, "index": 0})
    assert empty.status_code == 422 and "prints no text" in empty.get_json()["error"]


def test_the_preview_says_whether_jawas_wallrender_renders_it(client):
    body = preview(client)
    assert {k: body["target"][k] for k in ("version", "renders")} == {"version": "0.9", "renders": True}
    newer = copy.deepcopy(TEMPLATE)
    newer["layers"][0]["weight"] = "bold"
    body = preview(client, newer)
    render = body["renders"][0]
    assert {k: body["target"][k] for k in ("version", "renders")} == {"version": "0.9", "renders": False}  # weight came in 0.12
    assert render["kinds"][0] == "target" and "needs wallrender 0.12.0" in render["warnings"][0]
    assert len(render["kinds"]) == len(render["warnings"])


def test_the_package_names_the_sha256_jawas_store_shows(client):
    resp = client.post("/api/template/package", json={"template": TEMPLATE})
    assert resp.status_code == 200
    digest = resp.headers["X-Template-SHA256"]
    package = json.loads(resp.data)
    # JAWA's store writes template.json as json.dumps(template, indent=2) + "\n"
    # and logs the sha256 of those bytes.
    stored = (json.dumps(package["template"], indent=2) + "\n").encode()
    assert digest == hashlib.sha256(stored).hexdigest()
    assert len(digest) == 64


SPLIT = copy.deepcopy(TEMPLATE)
SPLIT["background"] = {"color": "#000000"}
SPLIT["layers"] = [{"type": "panel", "box": {"x": 0, "y": 0, "w": 0.5, "h": 1}, "color": "#FFFFFF"},
                   dict(TEMPLATE["layers"][1], text="{{device_name}}")]


def test_a_split_background_is_judged_by_its_worst_half(client):
    """White text over half white, half black: the mean is mid grey (about
    4:1 for white), but the white half reads at 1:1. Neither text colour
    passes over both halves, so the fix is a backdrop."""
    fix = preview(client, SPLIT)["renders"][0]["contrast"][0]
    assert fix["index"] == 1 and fix["ratio"] < 1.5 and fix["text"] is None


def test_a_backdrop_over_a_split_background_covers_the_bright_half(client):
    body = client.post("/api/template/backdrop",
                       json={"template": SPLIT, "values": VALUES, "index": 1}).get_json()
    panel = body["panel"]
    assert body["from"] < 1.5 and body["to"] >= 4.5
    # White text over white needs a dark panel at most of its strength;
    # the mean alone (mid grey) would have been satisfied by a faint one.
    assert panel["color"] == "#000000" and panel["opacity"] >= 0.5
    fixed = copy.deepcopy(SPLIT)
    fixed["layers"].insert(1, panel)
    assert contrast_warnings(fixed, VALUES, layer=2) == []


def test_each_role_render_carries_its_own_contrast_fix_and_values(client):
    """A role on a white background: its render's fix is worked out against
    white (dark text), not the sample's grey, and it says which values it used."""
    template = copy.deepcopy(TEMPLATE)
    template["layers"] = [dict(TEMPLATE["layers"][1], text="{{device_name}}")]
    template["background"] = {"color": "#0B2545"}
    template["roles"] = {"attribute": "Role", "variants": {"lobby": {"background": {"color": "#FFFFFF"}}}}
    resp = client.post("/api/template/preview",
                       json={"template": template, "values": VALUES, "stress": True})
    renders = {r["label"]: r for r in resp.get_json()["renders"]}
    assert renders["sample"]["contrast"] == [] and "values" not in renders["sample"]
    role = renders["role lobby"]
    assert role["values"] == dict(VALUES, role="lobby")
    assert role["contrast"][0]["text"]["name"] == "dark"
    assert renders["empty"]["values"] == {}
    body = client.post("/api/template/backdrop",
                       json={"template": template, "values": role["values"], "index": 0}).get_json()
    assert body["panel"]["color"] == "#000000" and body["to"] >= 4.5
