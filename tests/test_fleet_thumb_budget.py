"""The device check's thumbnail step: a budget, and it still looks the same."""

import statistics
import time

from PIL import Image, ImageChops, ImageStat

from views.template_api import THUMB_WIDTH, _thumb
from wallrender.render import _render

TEMPLATE = {
    "schema_version": 1, "canvas": {"width": 1290, "height": 2796}, "background": {"color": "#0B2545"},
    "layers": [
        {"type": "text", "text": "{{device_name}}", "box": {"x": 0.1, "y": 0.4, "w": 0.8, "h": 0.1},
         "size": 0.04, "color": "#FFFFFF"},
        {"type": "qr", "data": "jamf-device:{{jss_id}}", "box": {"x": 0.3, "y": 0.6, "w": 0.4, "h": 0.2}},
    ],
}


def full_render():
    return _render(TEMPLATE, {"device_name": "Front Desk iPhone", "jss_id": 42}, lambda _id: None)[0]


def test_the_thumbnail_step_takes_at_most_4_ms_per_device():
    image = full_render()
    times = []
    for _ in range(21):
        start = time.perf_counter()
        _thumb(image)
        times.append((time.perf_counter() - start) * 1000)
    # thumbnail() took 11.6 ms here.
    assert statistics.median(times) <= 4, f"median {statistics.median(times):.1f} ms"


def test_the_thumbnail_is_about_240_px_and_looks_like_the_old_one():
    image = full_render()
    thumb = _thumb(image)
    assert 200 <= thumb.width <= THUMB_WIDTH
    assert abs(thumb.height / thumb.width - image.height / image.width) < 0.01
    old = image.copy()
    old.thumbnail((THUMB_WIDTH, THUMB_WIDTH * 8))
    # At the size the sheet shows it (160 px tall), the two match.
    shown = (round(160 * image.width / image.height), 160)
    a, b = (t.convert("RGB").resize(shown, Image.LANCZOS) for t in (thumb, old))
    assert max(ImageStat.Stat(ImageChops.difference(a, b)).mean) < 3


def test_a_small_canvas_is_not_shrunk_past_its_width():
    small = Image.new("RGB", (200, 400))
    assert _thumb(small).size == (200, 400)
