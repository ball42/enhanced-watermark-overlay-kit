"""Preview weight: a photo background previews as a JPEG, Download stays lossless,
and the navbar logo is small."""

import base64
import io
import json
import os
import re

from PIL import Image, ImageChops

import config
from wallrender import cli as wallrender_cli

PHOTO_TEMPLATE = {
    "schema_version": 1,
    "canvas": {"width": 1290, "height": 2796},
    "background": {"asset": "photo"},
    "layers": [
        {"type": "text", "text": "{{device_name}}", "box": {"x": 0.1, "y": 0.6, "w": 0.8, "h": 0.06},
         "size": 0.04, "color": "#FFFFFF"},
        {"type": "qr", "data": "{{serial_number}}", "box": {"x": 0.35, "y": 0.75, "w": 0.3, "h": 0.14}},
    ],
}
VALUES = {"device_name": "Room 214 iPad", "serial_number": "DMPXK2ABCD"}


def grainy_photo():
    """A 1290x2796 JPEG with film grain, as hard to compress as a real photo."""
    w, h = 1290, 2796
    ramp = Image.linear_gradient("L").resize((w, h))
    mid = Image.new("L", (w, h), 128)
    channels = [ImageChops.add(ramp, ImageChops.subtract(Image.effect_noise((w, h), 40 + 10 * i), mid), 1, 0)
                for i in range(3)]
    buffer = io.BytesIO()
    Image.merge("RGB", channels).save(buffer, "JPEG", quality=92)
    return buffer.getvalue()


def add_photo(client):
    resp = client.post("/api/template/assets", content_type="multipart/form-data",
                       data={"file": (io.BytesIO(grainy_photo()), "photo.jpg"), "id": "photo"})
    assert resp.status_code == 201


def test_a_photo_background_previews_as_a_jpeg_under_2_mb(client):
    add_photo(client)
    resp = client.post("/api/template/preview", json={"template": PHOTO_TEMPLATE, "values": VALUES})
    assert resp.status_code == 200
    assert len(resp.get_data()) < 2_000_000
    image = resp.get_json()["renders"][0]["image"]
    assert image.startswith("data:image/jpeg;base64,")
    with Image.open(io.BytesIO(base64.b64decode(image.split(",", 1)[1]))) as img:
        assert img.size == (1290, 2796)


def test_a_role_photo_background_previews_as_a_jpeg(client):
    add_photo(client)
    template = dict(PHOTO_TEMPLATE, background={"color": "#0B2545"},
                    roles={"variants": {"staff": {"background": {"asset": "photo"}}}})
    sample, role = client.post("/api/template/preview", json={
        "template": template, "values": VALUES, "stress": True}).get_json()["renders"][::3]
    assert sample["image"].startswith("data:image/png;")
    assert role["label"] == "role staff" and role["image"].startswith("data:image/jpeg;")


def test_download_png_is_lossless_and_equals_wallrender_preview(client, tmp_path):
    add_photo(client)
    resp = client.post("/api/template/preview.png", json={"template": PHOTO_TEMPLATE, "values": VALUES})
    assert resp.status_code == 200 and resp.mimetype == "image/png"
    (tmp_path / "t.json").write_text(json.dumps(PHOTO_TEMPLATE))
    (tmp_path / "v.json").write_text(json.dumps(VALUES))
    out = tmp_path / "cli.png"
    code = wallrender_cli.main(["preview", str(tmp_path / "t.json"), str(tmp_path / "v.json"),
                                "-o", str(out), "--assets", config.TEMPLATE_ASSETS_FOLDER])
    assert code == 0
    with Image.open(io.BytesIO(resp.get_data()), formats=["PNG"]) as got, \
            Image.open(out, formats=["PNG"]) as want:
        assert got.size == want.size == (1290, 2796)
        assert ImageChops.difference(got.convert("RGBA"), want.convert("RGBA")).getbbox() is None


def test_download_png_reports_problems(client):
    assert client.post("/api/template/preview.png", json={"template": {}, "values": {}}).status_code == 400
    assert client.post("/api/template/preview.png", json=[]).status_code == 400
    missing = dict(PHOTO_TEMPLATE, background={"asset": "nope"})
    assert client.post("/api/template/preview.png", json={"template": missing, "values": {}}).status_code == 422


def test_navbar_logo_is_small_and_sharp_at_2x(client):
    path = os.path.join(config.BASE_DIR, "static", "ewok-64.png")
    assert os.path.getsize(path) < 10_000
    with Image.open(path, formats=["PNG"]) as img:
        assert img.size == (64, 64)
    for page in ("/", "/template"):
        body = re.sub(r"\?v=[0-9a-f]{12}", "", client.get(page).get_data(as_text=True))  # the hash on each URL
        assert '<img src="/static/ewok-64.png" width="32" height="32" alt="">' in body
        assert '<img src="/static/ewok.png"' not in body
