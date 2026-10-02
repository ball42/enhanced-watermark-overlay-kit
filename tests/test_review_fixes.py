"""App fixes from the 2026-10-02 wrap-up review."""

import io
import json
import zipfile

import pytest
from PIL import Image

from tests.conftest import make_test_image
from tests.test_template_api import TEMPLATE, image_bytes, logo_template, upload


# --- local-only: no DNS rebinding, no cross-site writes -----------------------------


@pytest.mark.parametrize("host", ["evil.example", "evil.example:5055", "10.0.0.5:5055"])
def test_foreign_host_headers_are_refused(client, host):
    assert client.get("/", headers={"Host": host}).status_code == 403
    assert client.get("/api/template/assets", headers={"Host": host}).status_code == 403


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1:5055", "localhost:6001", "[::1]:5055"])
def test_local_hosts_work(client, host):
    assert client.get("/", headers={"Host": host}).status_code == 200


def test_cross_site_form_posts_are_refused(client):
    data = {"file": (image_bytes((10, 10), "PNG"), "logo.png")}
    resp = client.post("/api/template/assets", data=data, content_type="multipart/form-data",
                       headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"})
    assert resp.status_code == 403
    assert client.get("/api/template/assets").get_json()["assets"] == []


def test_same_origin_posts_still_work(client):
    data = {"file": (image_bytes((10, 10), "PNG"), "logo.png")}
    resp = client.post("/api/template/assets", data=data, content_type="multipart/form-data",
                       headers={"Sec-Fetch-Site": "same-origin", "Origin": "http://127.0.0.1:5055"})
    assert resp.status_code == 201


# --- import only takes what the template uses -----------------------------------------


def bundle(template, files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("t.json", json.dumps(template))
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def import_file(client, data, name):
    return client.post("/api/template/import", data={"file": (io.BytesIO(data), name)},
                       content_type="multipart/form-data")


def test_import_ignores_assets_the_template_does_not_use(client):
    upload(client, "unrelated.png")
    before = client.get("/api/template/assets/unrelated").data
    data = bundle(logo_template(), {"logo.png": make_test_image(10, 10).getvalue(),
                                    "unrelated.png": make_test_image(30, 30).getvalue()})
    body = import_file(client, data, "x.zip").get_json()
    assert body["assets"] == ["logo"]
    assert any("unrelated.png" in s and "not used" in s for s in body["skipped"])
    assert client.get("/api/template/assets/unrelated").data == before


def test_import_reports_replaced_assets(client):
    upload(client, "logo.png")
    data = bundle(logo_template(), {"logo.png": make_test_image(12, 12).getvalue()})
    body = import_file(client, data, "x.zip").get_json()
    assert body["replaced"] == ["logo"]


def test_corrupt_zip_is_a_400(client):
    data = bytearray(bundle(logo_template(), {"logo.png": make_test_image(10, 10).getvalue()}))
    i = data.find(b"logo.png", 40) + 20
    data[i:i + 8] = b"\x00" * 8  # damage the compressed entry
    assert import_file(client, bytes(data), "x.zip").status_code == 400


@pytest.mark.parametrize("path", ["/api/template/preview", "/api/template/export", "/api/template/package"])
def test_deeply_nested_json_is_a_400(client, path):
    body = "[" * 50000 + "]" * 50000
    resp = client.post(path, data=body, content_type="application/json")
    assert resp.status_code == 400


def test_deeply_nested_json_import_is_a_400(client):
    assert import_file(client, ("[" * 50000 + "]" * 50000).encode(), "t.json").status_code == 400


# --- preview limits -------------------------------------------------------------------


def test_device_list_is_capped(client):
    resp = client.post("/api/template/preview", json={"template": TEMPLATE, "values": {},
                                                      "devices": ["iphone-6.7"] * 51})
    assert resp.status_code == 400


def test_stress_preview_still_returns_three_renders(client):
    body = client.post("/api/template/preview", json={"template": TEMPLATE, "values": {},
                                                      "stress": True}).get_json()
    assert [r["label"] for r in body["renders"]] == ["sample", "long", "empty"]


# --- asset library and photo mode -----------------------------------------------------


def test_a_bad_file_in_the_library_is_skipped(client, app):
    import config
    import os

    upload(client, "logo.png")
    with open(os.path.join(config.TEMPLATE_ASSETS_FOLDER, "broken.png"), "wb") as handle:
        handle.write(b"not a png")
    resp = client.get("/api/template/assets")
    assert resp.status_code == 200
    assert [a["id"] for a in resp.get_json()["assets"]] == ["logo"]


def _upload_photo(client, size=(80, 80)):
    buf = make_test_image(*size)
    return client.post("/api/upload", data={"file": (buf, "a.png")},
                       content_type="multipart/form-data").get_json()["filename"]


@pytest.mark.parametrize("resize", [100000, -5, "big", 0])
def test_photo_resize_is_clamped_or_refused(client, resize):
    name = _upload_photo(client)
    resp = client.post("/api/process", json={"filename": name, "resize": resize})
    if resp.status_code == 200:
        w, h = resp.get_json()["dimensions"].values()
        assert w * h <= 80 * 4 * 80 * 4
    else:
        assert resp.status_code == 400


def test_huge_photo_uploads_are_refused(client, monkeypatch):
    import views.api as api

    monkeypatch.setattr(api, "MAX_PHOTO_PIXELS", 100)
    data = {"file": (make_test_image(20, 20), "big.png")}
    resp = client.post("/api/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 400
