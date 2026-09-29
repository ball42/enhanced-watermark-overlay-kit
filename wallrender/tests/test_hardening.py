"""Hardening from the PR #1 security review: wallrender runs inside JAWA on
admin-uploaded templates and Jamf values, so hostile input must fail fast
with TemplateError and never exhaust CPU or memory."""

import io
import json
import threading
import time

import pytest
from PIL import Image

from wallrender import TemplateError, lint, render, validate

CANVAS = {"width": 1290, "height": 2796}


def tpl(*layers, background=None, canvas=CANVAS):
    t = {"schema_version": 1, "background": background or {"color": "#000000"}, "layers": list(layers)}
    if canvas is not None:
        t["canvas"] = canvas
    return t


def text(s, box=(0.1, 0.5, 0.8, 0.1), size=0.05, **kw):
    x, y, w, h = box
    return {"type": "text", "text": s, "box": {"x": x, "y": y, "w": w, "h": h}, "size": size, "color": "#FFFFFF", **kw}


def png(w, h, colour=(200, 0, 0, 255), mode="RGBA", fmt="PNG", **save):
    buf = io.BytesIO()
    Image.new(mode, (w, h), colour).save(buf, fmt, **save)
    return buf.getvalue()


def no_assets(aid):
    raise KeyError(aid)


def fast(fn, limit):
    start = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - start
    assert elapsed < limit, f"took {elapsed:.1f}s"
    return result


# --- C1: CPU -------------------------------------------------------------------

def test_huge_substituted_value_renders_fast():
    fast(lambda: render(tpl(text("{{d}}")), {"d": "x" * 1_000_000}, no_assets), 2)


def test_hostile_shrink_to_fit_is_bounded():
    layer = text("W" * 500, box=(0, 0, 0.0001, 0.1), size=0.5)
    fast(lambda: render(tpl(*[layer] * 10), {}, no_assets), 3)


# --- C2 / I2: memory and formats -------------------------------------------------

def test_extreme_aspect_asset_is_refused_without_a_huge_resize():
    with pytest.raises(TemplateError, match="aspect"):
        fast(lambda: render(tpl(background={"asset": "bg"}), {}, lambda a: png(3000, 1)), 2)


def test_oversized_asset_is_refused_before_decoding():
    big = png(7000, 7000, (0, 0, 0), mode="RGB")  # 49 MP > 40 MP cap, tiny on disk
    with pytest.raises(TemplateError, match="too large"):
        render(tpl(background={"asset": "bg"}, canvas=None), {}, lambda a: big)


def test_oversized_pil_image_from_resolver_is_refused():
    with pytest.raises(TemplateError, match="too large"):
        render(tpl(background={"asset": "bg"}, canvas=None), {}, lambda a: Image.new("RGB", (9000, 9000)))


@pytest.mark.parametrize("fmt", ["GIF", "TIFF", "BMP"])
def test_only_png_and_jpeg_assets_are_accepted(fmt):
    data = png(10, 10, (0, 0, 0), mode="RGB", fmt=fmt)
    with pytest.raises(TemplateError, match="PNG or JPEG"):
        render(tpl(background={"asset": "bg"}), {}, lambda a: data)


def test_eps_is_never_handed_to_ghostscript():
    eps = b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 10 10\nshowpage\n"
    with pytest.raises(TemplateError, match="PNG or JPEG"):
        render(tpl(background={"asset": "bg"}), {}, lambda a: eps)


def test_each_asset_is_decoded_once_per_render():
    calls = []
    layer = {"type": "image", "asset": "logo", "box": {"x": 0, "y": 0, "w": 0.2, "h": 0.1}}
    render(tpl(layer, layer, layer), {}, lambda a: calls.append(a) or png(20, 10))
    assert calls == ["logo"]


# --- I1 / I3 / M4 / M7: validation never crashes, render only raises TemplateError --

BAD_TEMPLATES = [
    {**tpl(), "canvas": "abc"},
    {**tpl(), "canvas": [1]},
    tpl(text("x", font=[])),
    tpl(text("x", align={})),
    json.loads('{"schema_version": 1, "canvas": {"width": 10, "height": 10}, "background": {"color": "#000000"},'
               ' "layers": [{"type": "text", "text": "x", "size": 0.1, "box": {"x": 0, "y": 0, "w": NaN, "h": 0.1}}]}'),
    tpl({"type": "image", "asset": "logo\n", "box": {"x": 0, "y": 0, "w": 1, "h": 1}}),
    tpl({"type": "image", "asset": 1, "box": {"x": 0, "y": 0, "w": 1, "h": 1}}),
    {**tpl(), "schema_version": True},
    tpl(canvas={"width": True, "height": 10}),
    tpl(background={"color": None}),
    tpl(text("x", color="#FFFFFF\n")),
    tpl(text("{{a\nb}}")),
]


@pytest.mark.parametrize("bad", BAD_TEMPLATES)
def test_bad_templates_are_rejected_without_crashing(bad):
    assert validate(bad), "validate must report a problem"
    with pytest.raises(TemplateError):
        render(bad, {}, no_assets)


@pytest.mark.parametrize("values, layer", [
    ({"n": 10 ** 5000}, text("{{n}}")),
    ({"d": "x" * 5000}, {"type": "qr", "data": "{{d}}", "box": {"x": 0, "y": 0, "w": 0.5, "h": 0.5}}),
    ({"d": "\ud800"}, {"type": "qr", "data": "{{d}}", "box": {"x": 0, "y": 0, "w": 0.5, "h": 0.5}}),
])
def test_hostile_values_never_escape_as_other_exceptions(values, layer):
    try:
        render(tpl(layer), values, no_assets)
    except TemplateError:
        pass


def test_non_scalar_values_are_treated_as_missing():
    """{{location}} must not print the whole Jamf subtree onto a lock screen."""
    img = render(tpl(text("{{location}}")), {"location": {"building": "N", "secret": "s"}}, no_assets)
    assert img.convert("L").getbbox() is None
    assert any("location" in w for w in lint(tpl(text("{{location}}")), {"location": {"a": 1}}, no_assets))


# --- I4: thread safety ------------------------------------------------------------

def test_concurrent_renders_are_identical():
    t = tpl(text("{{n}}", size=0.03), text("{{n}}", box=(0.1, 0.7, 0.8, 0.1), size=0.08))
    results, errors = [], []

    def work(i):
        try:
            results.append(render(t, {"n": "Device 7"}, no_assets).tobytes())
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert not errors and len(set(results)) == 1


# --- M1 / M3: defined output ---------------------------------------------------------

def test_transparent_background_renders_black():
    img = render(tpl(background={"asset": "bg"}), {}, lambda a: png(10, 20, (0, 255, 0, 0)))
    assert img.getpixel((5, 5)) == (0, 0, 0)


def test_jpeg_exif_orientation_is_applied():
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 CW on display
    data = png(100, 50, (0, 0, 0), mode="RGB", fmt="JPEG", exif=exif.tobytes())
    img = render({"schema_version": 1, "background": {"asset": "bg"}, "layers": []}, {}, lambda a: data)
    assert img.size == (50, 100)
