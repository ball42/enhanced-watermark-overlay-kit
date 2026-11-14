"""The device check's "Fit the longest name": /api/template/fit-names works
out the size a name layer needs so the names that shrank print at full size."""

import copy
import math

import wallrender
from wallrender.render import READABLE_MIN

TEMPLATE = {
    "schema_version": 1,
    "canvas": {"width": 1290, "height": 2796},
    "background": {"color": "#0B2545"},
    "layers": [
        {"type": "text", "text": "{{device_name}}", "box": {"x": 0.1, "y": 0.5, "w": 0.8, "h": 0.05},
         "size": 0.04, "color": "#FFFFFF", "align": "center"},
        {"type": "text", "text": "{{asset_tag}}", "box": {"x": 0.1, "y": 0.6, "w": 0.8, "h": 0.05},
         "size": 0.02, "color": "#FFFFFF", "align": "center"},
    ],
}
LONG = [{"device_name": "Room-214-Science-Lab-Cart-" + "W" * n} for n in (6, 10, 14)]


def shrink_warnings(template, values):
    warnings = wallrender.lint(template, values, lambda _id: b"")
    return [w for w in warnings if w.startswith("layer 0:") and ("shrank" in w or "cut off" in w
                                                                 or "shortened" in w)]


def fit(client, template, devices, layers=(0,)):
    return client.post("/api/template/fit-names",
                       json={"template": template, "layers": list(layers), "devices": devices})


def test_the_fitted_size_prints_every_long_name_without_shrinking(client):
    assert all(shrink_warnings(TEMPLATE, d) for d in LONG)  # they shrink now
    resp = fit(client, TEMPLATE, LONG)
    assert resp.status_code == 200
    (layer,) = resp.get_json()["layers"]
    assert layer["index"] == 0 and layer["from"] == 0.04
    assert layer["changed"] and layer["fits"]
    assert 0 < layer["size"] < 0.04
    assert round(layer["size"], 3) == layer["size"]  # a step of the size field
    fitted = copy.deepcopy(TEMPLATE)
    fitted["layers"][0]["size"] = layer["size"]
    assert [shrink_warnings(fitted, d) for d in LONG] == [[], [], []]


def test_names_that_already_fit_change_nothing(client):
    (layer,) = fit(client, TEMPLATE, [{"device_name": "Mac-01"}]).get_json()["layers"]
    assert layer == {**layer, "changed": False, "fits": True, "size": 0.04}


def test_a_smallest_size_above_the_fit_comes_down_with_it(client):
    template = copy.deepcopy(TEMPLATE)
    template["layers"][0]["min_size"] = 0.035
    (layer,) = fit(client, template, LONG).get_json()["layers"]
    assert layer["changed"] and layer["min_size"] == layer["size"]


def test_a_name_too_long_to_read_at_any_fitting_size_is_not_shrunk(client):
    template = copy.deepcopy(TEMPLATE)
    template["layers"][0]["box"]["w"] = 0.2
    (layer,) = fit(client, template, [{"device_name": "W" * 60}]).get_json()["layers"]
    assert layer["fits"] is False and layer["changed"] is False
    assert layer["readable_px"] == math.ceil(READABLE_MIN * 2796)


def test_bad_requests_are_refused(client):
    assert fit(client, TEMPLATE, []).status_code == 400
    assert fit(client, TEMPLATE, LONG, layers=(5,)).status_code == 400
    assert fit(client, TEMPLATE, LONG, layers=("0",)).status_code == 400
    broken = copy.deepcopy(TEMPLATE)
    broken["layers"][0]["box"]["x"] = 0.9
    assert "problems" in fit(client, broken, LONG).get_json()
    assert fit(client, TEMPLATE, [{"device_name": "x"}] * 201).status_code == 400
