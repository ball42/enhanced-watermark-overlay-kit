"""Overflow policy: what a text layer does with long or empty values."""

import json

import pytest
from PIL import Image

from wallrender import lint, render, validate
from wallrender.cli import main

from test_render import ink_bbox, no_assets, text_layer, tpl


# --- validation --------------------------------------------------------------


@pytest.mark.parametrize(
    "extra, ok",
    [
        ({"overflow": "shrink"}, True),
        ({"overflow": "ellipsis"}, True),
        ({"overflow": "wrap"}, False),
        ({"min_size": 0.02}, True),
        ({"min_size": 0.06}, False),  # above size (0.05)
        ({"min_size": 0}, False),
        ({"min_size": True}, False),
        ({"hide_if_empty": True}, True),
        ({"hide_if_empty": "yes"}, False),
    ],
)
def test_text_overflow_fields_are_validated(extra, ok):
    problems = validate(tpl(text_layer("x", **extra)))
    assert (problems == []) is ok, problems


def test_qr_hide_if_empty_is_validated():
    qr = {"type": "qr", "data": "{{x}}", "box": {"x": 0, "y": 0, "w": 0.5, "h": 0.5}}
    assert validate(tpl({**qr, "hide_if_empty": True})) == []
    assert validate(tpl({**qr, "hide_if_empty": 1}))


# --- hide_if_empty -----------------------------------------------------------


def test_label_with_an_empty_value_is_hidden():
    layer = text_layer("Asset {{asset_tag}}", hide_if_empty=True)
    assert ink_bbox(render(tpl(layer), {"asset_tag": ""}, no_assets)) is None


def test_label_with_a_value_still_shows():
    layer = text_layer("Asset {{asset_tag}}", hide_if_empty=True)
    assert ink_bbox(render(tpl(layer), {"asset_tag": "HR-1"}, no_assets))


def test_hidden_if_any_variable_is_empty():
    layer = text_layer("{{a}} / {{b}}", hide_if_empty=True)
    assert ink_bbox(render(tpl(layer), {"a": "x"}, no_assets)) is None


def test_without_the_flag_the_label_still_prints():
    layer = text_layer("Asset {{asset_tag}}")
    assert ink_bbox(render(tpl(layer), {}, no_assets))


def test_qr_hide_if_empty():
    qr = {"type": "qr", "data": "jamf-device:{{jss_id}}", "hide_if_empty": True,
          "box": {"x": 0.25, "y": 0.25, "w": 0.5, "h": 0.5}}
    assert ink_bbox(render(tpl(qr), {}, no_assets)) is None
    assert ink_bbox(render(tpl(qr), {"jss_id": 4}, no_assets))


def test_hidden_layer_still_lints_as_missing():
    layer = text_layer("Asset {{asset_tag}}", hide_if_empty=True)
    warnings = lint(tpl(layer), {}, no_assets)
    assert any("asset_tag" in w and "hidden" in w for w in warnings), warnings


# --- ellipsis and min_size ---------------------------------------------------

LONG = "W" * 60


def test_shrink_respects_min_size():
    """With a floor, shrink stops there; the overflow is cut off and linted."""
    floor = text_layer("{{n}}", min_size=0.03)
    warnings = lint(tpl(floor), {"n": LONG}, no_assets)
    assert any("cut off" in w for w in warnings), warnings


def test_ellipsis_keeps_the_text_inside_its_box():
    layer = text_layer("{{n}}", overflow="ellipsis", min_size=0.03)
    img = render(tpl(layer), {"n": LONG}, no_assets)
    left, top, right, bottom = ink_bbox(img)
    # box is x 0.1..0.9 of 400px wide
    assert left >= 40 and right <= 360


def test_ellipsis_text_is_not_cut_off_and_is_reported_as_shortened():
    layer = text_layer("{{n}}", overflow="ellipsis", min_size=0.03)
    warnings = lint(tpl(layer), {"n": LONG}, no_assets)
    assert not any("cut off" in w for w in warnings)
    assert any("shortened with" in w for w in warnings), warnings


def test_ellipsis_without_min_size_never_shrinks():
    short = text_layer("Hi", overflow="ellipsis")
    long = text_layer("{{n}}", overflow="ellipsis")
    a = ink_bbox(render(tpl(short), {}, no_assets))
    b = ink_bbox(render(tpl(long), {"n": LONG}, no_assets))
    # same font size: same ink height
    assert (a[3] - a[1]) == pytest.approx(b[3] - b[1], abs=3)


def test_ellipsis_leaves_fitting_text_alone():
    plain = render(tpl(text_layer("Hi")), {}, no_assets)
    ell = render(tpl(text_layer("Hi", overflow="ellipsis")), {}, no_assets)
    assert plain.tobytes() == ell.tobytes()


def test_default_rendering_is_unchanged():
    """No overflow fields: identical pixels to an explicit 'shrink'."""
    a = render(tpl(text_layer("{{n}}")), {"n": LONG}, no_assets)
    b = render(tpl(text_layer("{{n}}", overflow="shrink")), {"n": LONG}, no_assets)
    assert a.tobytes() == b.tobytes()


# --- stress test in the CLI --------------------------------------------------


def test_stress_renders_long_and_empty_variants(tmp_path, capsys):
    t = tmp_path / "t.json"
    t.write_text(json.dumps(tpl(text_layer("{{device_name}}"), text_layer("Asset {{asset_tag}}", box=(0.1, 0.7, 0.8, 0.1), hide_if_empty=True))))
    v = tmp_path / "v.json"
    v.write_text(json.dumps({"device_name": "iPad", "asset_tag": "A1"}))
    out = tmp_path / "out.png"
    assert main(["preview", str(t), str(v), "-o", str(out), "--stress"]) == 0
    for name in ("out.png", "out-long.png", "out-empty.png"):
        with Image.open(tmp_path / name) as img:
            assert img.size == (400, 800)
    text = capsys.readouterr()
    assert "[long]" in text.err and "[empty]" in text.err
