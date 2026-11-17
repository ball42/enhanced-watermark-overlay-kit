"""The template API keeps decoded and resized assets between renders, so a
device check decodes a large logo once, not once per device."""

import importlib
import io
import os

import pytest
from PIL import Image, ImageDraw

import config
from views import template_api
from wallrender import render
from wallrender.cli import folder_assets

wr = importlib.import_module("wallrender.render")

TEMPLATE = {
    "schema_version": 1, "canvas": {"width": 300, "height": 600}, "background": {"color": "#0B2545"},
    "layers": [
        {"type": "text", "text": "{{device_name}}", "box": {"x": 0.1, "y": 0.6, "w": 0.8, "h": 0.05},
         "size": 0.04, "color": "#FFFFFF"},
        {"type": "image", "asset": "logo", "box": {"x": 0.25, "y": 0.2, "w": 0.5, "h": 0.3}},
    ],
}


def save_logo(color):
    img = Image.new("RGBA", (800, 800), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle((100, 100, 700, 700), fill=color)
    folder = config.TEMPLATE_ASSETS_FOLDER
    os.makedirs(folder, exist_ok=True)
    img.save(os.path.join(folder, "logo.png"))


@pytest.fixture()
def opened(monkeypatch):
    template_api.ASSET_CACHE.clear()
    calls = []
    original = wr._open
    monkeypatch.setattr(wr, "_open", lambda *a: calls.append(a[0]) or original(*a))
    yield calls
    template_api.ASSET_CACHE.clear()


def png_from(resp):
    return Image.open(io.BytesIO(resp.data)).convert("RGB")


def test_a_device_check_decodes_the_logo_once_across_its_chunks(client, opened):
    save_logo((200, 80, 20, 255))
    devices = [{"device_name": f"Device {n}"} for n in range(20)]
    for first in (1, 11):
        resp = client.post("/api/template/preview-batch",
                           json={"template": TEMPLATE, "devices": devices[first - 1:first + 9], "first": first})
        assert resp.status_code == 200
    resp = client.post("/api/template/preview", json={"template": TEMPLATE, "values": devices[0]})
    assert resp.status_code == 200
    assert opened == ["logo"]


def test_the_preview_matches_wallrender_preview_pixels(client, opened):
    save_logo((200, 80, 20, 255))
    values = {"device_name": "Front Desk iPhone"}
    client.post("/api/template/preview.png", json={"template": TEMPLATE, "values": values})  # warm
    cached = png_from(client.post("/api/template/preview.png", json={"template": TEMPLATE, "values": values}))
    plain = render(TEMPLATE, values, folder_assets(config.TEMPLATE_ASSETS_FOLDER))
    assert cached.tobytes() == plain.tobytes()


def test_a_replaced_logo_shows_in_the_next_preview(client, opened):
    values = {"device_name": "Front Desk iPhone"}
    middle = (150, 210)
    save_logo((255, 0, 0, 255))
    before = png_from(client.post("/api/template/preview.png", json={"template": TEMPLATE, "values": values}))
    save_logo((0, 0, 255, 255))
    after = png_from(client.post("/api/template/preview.png", json={"template": TEMPLATE, "values": values}))
    assert before.getpixel(middle) == (255, 0, 0)
    assert after.getpixel(middle) == (0, 0, 255)
