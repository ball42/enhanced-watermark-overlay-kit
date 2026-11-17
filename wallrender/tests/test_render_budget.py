"""Render cost budgets: an opaque canvas is not flattened over black, and an
AssetCache decodes and resizes an image layer once across many renders."""

import importlib
import io
import statistics
import time

from PIL import Image, ImageDraw

from wallrender import AssetCache, render

wr = importlib.import_module("wallrender.render")  # the module, not render()

# The template a new design starts from in EWOK: device name and a QR code
# on a colour background, at iPhone size.
DEFAULT = {
    "schema_version": 1, "canvas": {"width": 1290, "height": 2796}, "background": {"color": "#0B2545"},
    "layers": [
        {"type": "text", "text": "{{device_name}}", "box": {"x": 0.1, "y": 0.6, "w": 0.8, "h": 0.05},
         "size": 0.028, "color": "#FFFFFF", "align": "center"},
        {"type": "qr", "data": "jamf-device:{{jss_id}}", "box": {"x": 0.35, "y": 0.66, "w": 0.3, "h": 0.14}},
    ],
}
VALUES = {"device_name": "Front Desk iPhone", "jss_id": 42}


def no_assets(asset_id):
    raise KeyError(asset_id)


def png(img):
    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    return buffer.getvalue()


def logo(side, color=(200, 80, 20, 220)):
    img = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((side // 8, side // 8, side * 7 // 8, side * 7 // 8), fill=color)
    return png(img)


def with_logo(background=None):
    return {**DEFAULT, "background": background or DEFAULT["background"],
            "layers": DEFAULT["layers"] + [{"type": "image", "asset": "logo",
                                            "box": {"x": 0.35, "y": 0.3, "w": 0.3, "h": 0.14}}]}


def test_the_default_template_renders_within_its_budget():
    # 33.6 ms before an opaque canvas skipped the flatten (about 9 ms after),
    # so the bound has room for a loaded machine.
    for _ in range(3):
        render(DEFAULT, VALUES, no_assets)
    times = []
    for _ in range(15):
        start = time.perf_counter()
        render(DEFAULT, VALUES, no_assets)
        times.append(time.perf_counter() - start)
    assert statistics.median(times) * 1000 <= 22


def test_an_opaque_canvas_is_not_composited_over_black(monkeypatch):
    calls = []
    original = Image.Image.alpha_composite

    def counting(self, im, *args, **kwargs):
        calls.append(im.size)
        return original(self, im, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "alpha_composite", counting)
    render(DEFAULT, VALUES, no_assets)
    assert (1290, 2796) not in calls  # layers composite their own boxes only
    calls.clear()
    render({**DEFAULT, "background": {"color": "#0B254580"}}, VALUES, no_assets)
    assert (1290, 2796) in calls  # a translucent canvas is still flattened


def test_skipping_the_flatten_changes_no_pixel():
    base = Image.new("RGBA", (64, 64), (11, 37, 69, 255))
    for alpha in (1, 64, 128, 200, 254, 255):
        spot = Image.new("RGBA", (16, 16), (250, 120, 7, alpha))
        base.alpha_composite(spot, ((alpha % 3) * 16, (alpha % 4) * 16))
    assert wr._flatten(base, True).tobytes() == wr._flatten(base, False).tobytes()


def test_a_translucent_background_still_renders_over_black():
    img = render({**DEFAULT, "background": {"color": "#FFFFFF80"}, "layers": []}, {}, no_assets)
    assert img.mode == "RGB"
    assert img.getpixel((0, 0)) == (128, 128, 128)


def test_opacity_is_known_from_the_asset_itself():
    jpeg = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(jpeg, "JPEG")
    assert wr._open("a", jpeg.getvalue())[1] is True
    assert wr._open("a", png(Image.new("RGBA", (8, 8), (1, 2, 3, 255))))[1] is True
    assert wr._open("a", logo(8))[1] is False


def test_a_photo_background_with_a_hole_still_renders_black_there():
    photo = Image.new("RGBA", (1290, 2796), (90, 140, 200, 255))
    photo.paste((0, 0, 0, 0), (0, 0, 100, 100))
    data = png(photo)
    img = render({**DEFAULT, "background": {"asset": "bg"}, "layers": []}, {}, lambda _: data)
    assert img.getpixel((10, 10)) == (0, 0, 0)
    assert img.getpixel((500, 500)) == (90, 140, 200)


def test_a_cache_decodes_and_resizes_an_image_layer_once(monkeypatch):
    data = logo(2000)
    opened, resized = [], []
    original_open, original_resize = wr._open, Image.Image.resize
    monkeypatch.setattr(wr, "_open", lambda *a: opened.append(a[0]) or original_open(*a))

    def counting_resize(self, size, *args, **kwargs):
        if self.size == (2000, 2000) and self.mode == "RGBA":  # not Pillow's own RGBa pass
            resized.append(size)
        return original_resize(self, size, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "resize", counting_resize)
    cache = AssetCache()
    for n in range(10):
        render(with_logo(), {"device_name": f"Device {n}", "jss_id": n}, lambda _: data, cache=cache)
    assert len(opened) == 1 and len(resized) == 1
    render(with_logo(), VALUES, lambda _: data)  # no cache: decoded again, as before
    assert len(opened) == 2


def test_cached_renders_match_uncached_ones():
    data = logo(600)
    cache = AssetCache()
    plain = render(with_logo(), VALUES, lambda _: data)
    first = render(with_logo(), VALUES, lambda _: data, cache=cache)
    second = render(with_logo(), VALUES, lambda _: data, cache=cache)
    assert plain.tobytes() == first.tobytes() == second.tobytes()


def test_a_replaced_asset_is_never_drawn_from_the_cache():
    cache = AssetCache()
    box = (645, 1035)  # the middle of the logo's box
    old = render(with_logo(), VALUES, lambda _: logo(600, (255, 0, 0, 255)), cache=cache)
    new = render(with_logo(), VALUES, lambda _: logo(600, (0, 0, 255, 255)), cache=cache)
    assert old.getpixel(box) == (255, 0, 0)
    assert new.getpixel(box) == (0, 0, 255)


def test_the_cache_stays_within_its_byte_bound():
    cache = AssetCache(max_bytes=100)
    cache.put(("a",), "A", 60)
    cache.put(("b",), "B", 60)  # over the bound: the oldest goes
    assert cache.get(("a",)) is None and cache.get(("b",)) == "B"
    cache.put(("huge",), "H", 101)  # never held at all
    assert cache.get(("huge",)) is None and cache.get(("b",)) == "B"
