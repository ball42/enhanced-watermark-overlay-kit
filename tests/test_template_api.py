"""Template mode T1: preview renders and the template asset library."""

import base64
import io

import pytest
from PIL import Image

from tests.conftest import make_test_image

TEMPLATE = {
    "schema_version": 1,
    "canvas": {"width": 300, "height": 600},
    "background": {"color": "#0B2545"},
    "layers": [
        {"type": "text", "text": "{{device_name}}", "box": {"x": 0.1, "y": 0.4, "w": 0.8, "h": 0.1},
         "size": 0.04, "color": "#FFFFFF"},
    ],
}


def decode(data_url):
    assert data_url.startswith("data:image/png;base64,")
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1])))


# --- preview -----------------------------------------------------------------


def test_preview_returns_a_png_and_warnings(client):
    resp = client.post("/api/template/preview", json={"template": TEMPLATE, "values": {}})
    assert resp.status_code == 200
    renders = resp.get_json()["renders"]
    assert [r["label"] for r in renders] == ["sample"]
    with decode(renders[0]["image"]) as img:
        assert img.size == (300, 600)
    assert any("device_name" in w for w in renders[0]["warnings"])


def test_preview_stress_adds_long_and_empty(client):
    resp = client.post("/api/template/preview",
                       json={"template": TEMPLATE, "values": {"device_name": "iPad"}, "stress": True})
    labels = [r["label"] for r in resp.get_json()["renders"]]
    assert labels == ["sample", "long", "empty"]


def test_invalid_template_returns_its_problems(client):
    resp = client.post("/api/template/preview", json={"template": {"schema_version": 9}, "values": {}})
    assert resp.status_code == 400
    assert any("schema_version" in p for p in resp.get_json()["problems"])


@pytest.mark.parametrize("body", [None, [], {"template": TEMPLATE}, {"template": TEMPLATE, "values": []}])
def test_malformed_request_is_400(client, body):
    resp = client.post("/api/template/preview", json=body)
    assert resp.status_code == 400


def test_missing_asset_is_422_with_the_id(client):
    template = dict(TEMPLATE, background={"asset": "nope"})
    template.pop("canvas")
    resp = client.post("/api/template/preview", json={"template": template, "values": {}})
    assert resp.status_code == 422
    assert any("nope" in p for p in resp.get_json()["problems"])


# --- asset library -----------------------------------------------------------


def image_bytes(size, fmt):
    if fmt == "PNG":
        return make_test_image(*size, fmt=fmt)
    buffer = io.BytesIO()
    Image.new("RGB", size, (255, 0, 0)).save(buffer, fmt)  # JPEG and GIF need no alpha
    buffer.seek(0)
    return buffer


def upload(client, name="logo.png", fmt="PNG", asset_id=None, size=(40, 30)):
    data = {"file": (image_bytes(size, fmt), name)}
    if asset_id is not None:
        data["id"] = asset_id
    return client.post("/api/template/assets", data=data, content_type="multipart/form-data")


def test_upload_lists_and_serves_an_asset(client):
    resp = upload(client, "Company Logo.PNG")
    assert resp.status_code == 201
    assert resp.get_json() == {"id": "company-logo", "width": 40, "height": 30}
    assert client.get("/api/template/assets").get_json()["assets"] == [
        {"id": "company-logo", "width": 40, "height": 30}
    ]
    served = client.get("/api/template/assets/company-logo")
    assert served.status_code == 200
    assert served.mimetype == "image/png"


def test_uploaded_asset_is_used_by_preview(client):
    upload(client, "bg.png", size=(60, 120))
    template = dict(TEMPLATE, background={"asset": "bg"})
    template.pop("canvas")
    resp = client.post("/api/template/preview", json={"template": template, "values": {}})
    assert resp.status_code == 200
    with decode(resp.get_json()["renders"][0]["image"]) as img:
        assert img.size == (60, 120)


def test_jpeg_is_accepted_and_replaces_a_png_of_the_same_id(client):
    upload(client, "logo.png")
    resp = upload(client, "logo.jpg", fmt="JPEG")
    assert resp.status_code == 201
    assert [a["id"] for a in client.get("/api/template/assets").get_json()["assets"]] == ["logo"]
    assert client.get("/api/template/assets/logo").mimetype == "image/jpeg"


def test_explicit_id_wins_over_the_filename(client):
    assert upload(client, "whatever.png", asset_id="brand").get_json()["id"] == "brand"


@pytest.mark.parametrize("asset_id", ["../x", "UPPER", "a" * 65, "with space"])
def test_bad_explicit_ids_are_rejected(client, asset_id):
    assert upload(client, asset_id=asset_id).status_code == 400


def test_non_png_or_jpeg_is_rejected(client):
    resp = upload(client, "pic.gif", fmt="GIF")
    assert resp.status_code == 400
    assert "PNG or JPEG" in resp.get_json()["error"]


def test_a_lying_extension_is_judged_by_content(client):
    assert upload(client, "fake.png", fmt="GIF").status_code == 400


def test_not_an_image_is_rejected(client):
    data = {"file": (io.BytesIO(b"hello"), "x.png")}
    resp = client.post("/api/template/assets", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_delete_asset(client):
    upload(client, "logo.png")
    assert client.delete("/api/template/assets/logo").status_code == 204
    assert client.get("/api/template/assets").get_json()["assets"] == []
    assert client.delete("/api/template/assets/logo").status_code == 404


@pytest.mark.parametrize("asset_id", ["..", "%2e%2e%2fconfig", "UPPER"])
def test_serving_rejects_odd_ids(client, asset_id):
    assert client.get(f"/api/template/assets/{asset_id}").status_code == 404
