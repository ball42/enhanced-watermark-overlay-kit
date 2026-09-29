"""wallrender: one renderer for EWOK's preview and JAWA Brander's per-device render."""

import io

import pytest
from PIL import Image

from wallrender import TemplateError, lint, render, validate

BLACK_BG = {"schema_version": 1, "canvas": {"width": 400, "height": 800}, "background": {"color": "#000000"}}


def tpl(*layers, **extra):
    return {**BLACK_BG, "layers": list(layers), **extra}


def text_layer(text, box=(0.1, 0.5, 0.8, 0.1), **kw):
    x, y, w, h = box
    return {"type": "text", "text": text, "box": {"x": x, "y": y, "w": w, "h": h},
            "size": 0.05, "color": "#FFFFFF", "align": "center", **kw}


def ink_bbox(img):
    """Bounding box of anything that isn't the black background."""
    return img.convert("L").point(lambda v: 255 if v > 40 else 0).getbbox()


def no_assets(asset_id):
    raise KeyError(asset_id)


def test_text_is_drawn_inside_its_box():
    img = render(tpl(text_layer("Chris's iPad", box=(0.1, 0.5, 0.8, 0.1))), {}, no_assets)
    assert img.size == (400, 800)
    left, top, right, bottom = ink_bbox(img)
    assert 40 <= left and right <= 360 and 400 <= top and bottom <= 480


def test_variables_are_substituted_and_missing_ones_render_empty():
    with_value = render(tpl(text_layer("{{device_name}}")), {"device_name": "Kiosk 7"}, no_assets)
    missing = render(tpl(text_layer("{{device_name}}")), {}, no_assets)
    assert ink_bbox(with_value) is not None
    assert ink_bbox(missing) is None  # missing value: empty, never the literal {{...}}


def test_dotted_paths_resolve_from_nested_values():
    img = render(tpl(text_layer("{{ location.building }}")), {"location": {"building": "North"}}, no_assets)
    assert ink_bbox(img) is not None


def test_text_uses_the_bundled_font_at_the_requested_size():
    img = render(tpl(text_layer("HHHH", box=(0, 0.4, 1, 0.2), size=0.05)), {}, no_assets)
    _, top, _, bottom = ink_bbox(img)
    cap_height = bottom - top
    assert 20 <= cap_height <= 40  # 5% of 800 = 40px em; cap height ~0.7em (a 10px bitmap fallback fails this)


def test_qr_code_is_square_and_inside_its_box():
    layer = {"type": "qr", "data": "jss:{{jss_id}}", "box": {"x": 0.25, "y": 0.1, "w": 0.5, "h": 0.5}}
    img = render(tpl(layer, background={"color": "#FFFFFF"}), {"jss_id": 42}, no_assets)
    dark = img.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()
    left, top, right, bottom = dark
    assert 100 <= left and right <= 300 and 80 <= top and bottom <= 480
    assert abs((right - left) - (bottom - top)) <= 2


def _png(w, h, colour):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), colour).save(buf, "PNG")
    return buf.getvalue()


def test_background_asset_sets_the_canvas_size():
    t = {"schema_version": 1, "background": {"asset": "bg"}, "layers": []}
    img = render(t, {}, lambda aid: _png(300, 600, (10, 20, 30)))
    assert img.size == (300, 600)
    assert img.getpixel((5, 5))[:3] == (10, 20, 30)


def test_image_layer_is_contained_in_its_box():
    layer = {"type": "image", "asset": "logo", "box": {"x": 0.5, "y": 0.0, "w": 0.5, "h": 0.25}}
    img = render(tpl(layer), {}, lambda aid: _png(100, 50, (255, 0, 0)))
    left, top, right, bottom = ink_bbox(img)
    assert 200 <= left and right <= 400 and top >= 0 and bottom <= 200


def test_rendering_is_deterministic():
    t = tpl(text_layer("{{serial_number}}"), {"type": "qr", "data": "x", "box": {"x": 0, "y": 0, "w": 0.3, "h": 0.3}})
    a = render(t, {"serial_number": "F9FXYZ"}, no_assets).tobytes()
    b = render(t, {"serial_number": "F9FXYZ"}, no_assets).tobytes()
    assert a == b


@pytest.mark.parametrize("bad, fragment", [
    ({**BLACK_BG, "schema_version": 2, "layers": []}, "schema_version"),
    (tpl({"type": "shell", "box": {"x": 0, "y": 0, "w": 1, "h": 1}}), "unknown layer type"),
    (tpl(text_layer("x", box=(0.5, 0.5, 0.8, 0.1))), "box"),
    ({**BLACK_BG, "canvas": {"width": 20000, "height": 20000}, "layers": []}, "canvas"),
    (tpl({"type": "image", "asset": "../etc/passwd", "box": {"x": 0, "y": 0, "w": 1, "h": 1}}), "asset"),
    (tpl(text_layer("x", color="red")), "color"),
    (tpl(*[text_layer("x")] * 51), "layers"),
    (tpl(text_layer("{{__class__.__init__}}")), "variable"),
])
def test_validate_rejects_bad_templates(bad, fragment):
    problems = validate(bad)
    assert any(fragment in p for p in problems), problems
    with pytest.raises(TemplateError):
        render(bad, {}, no_assets)


def test_lint_reports_missing_variables_and_glyphs():
    t = tpl(text_layer("{{device_name}} {{asset_tag}}"), text_layer("Rocket 🚀", box=(0.1, 0.7, 0.8, 0.1)))
    warnings = lint(t, {"device_name": "iPad"}, no_assets)
    assert any("asset_tag" in w for w in warnings)
    assert any("🚀" in w for w in warnings)


def test_lint_does_not_flag_ordinary_text():
    t = tpl(text_layer("Chris’s iPad — Room 204 (Nürnberg)"))
    assert lint(t, {}, no_assets) == []


def test_example_template_renders_with_the_sample_device():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "examples"
    template = json.loads((root / "brander-basic.json").read_text())
    values = json.loads((root / "sample-device.json").read_text())
    assert validate(template) == []
    img = render(template, values, no_assets)
    assert img.mode == "RGB" and img.size == (1290, 2796)
    assert lint(template, values, no_assets) == []
