"""Fixes from the 2026-10-02 wrap-up reviews (EWOK and JAWA)."""

import time

import pytest
from PIL import Image

from wallrender import lint, render, render_with_lint, validate
from wallrender.devices import fit_warnings

from test_render import ink_bbox, no_assets, text_layer, tpl


@pytest.mark.parametrize("field, value", [("screen", ["x"]), ("screen", {"a": 1}),
                                          ("person_fields", ["x"])])
def test_unhashable_values_are_problems_not_crashes(field, value):
    problems = validate(tpl(text_layer("x"), **{field: value}))
    assert any(field in p for p in problems)


def test_deeply_nested_values_do_not_crash_render():
    deep = {}
    node = deep
    for _ in range(5000):
        node["a"] = {}
        node = node["a"]
    render(tpl(text_layer("{{device_name}}")), deep, no_assets)  # no RecursionError


def test_lint_checks_glyphs_in_role_variant_text():
    t = tpl(text_layer("{{role.t}}"), roles={"variants": {"nurse": {"values": {"t": "Rocket 🚀"}}}})
    warnings = lint(t, {"role": "Nurse"}, no_assets)
    assert any("🚀" in w for w in warnings), warnings


def test_render_with_lint_matches_separate_calls():
    t = tpl(text_layer("{{device_name}}"))
    image, warnings = render_with_lint(t, {}, no_assets)
    assert image.tobytes() == render(t, {}, no_assets).tobytes()
    assert warnings == lint(t, {}, no_assets)


def test_lint_cost_stays_close_to_render_on_big_canvases():
    layers = [text_layer(f"Line {i}", box=(0, 0, 1, 1)) for i in range(20)]
    t = tpl(*layers, canvas={"width": 4000, "height": 4000})
    started = time.monotonic()
    render(t, {}, no_assets)
    render_time = time.monotonic() - started
    started = time.monotonic()
    render_with_lint(t, {}, no_assets)
    lint_time = time.monotonic() - started
    assert lint_time < render_time * 2.5 + 0.5


def test_ellipsis_also_fits_too_many_lines():
    many = "\n".join(f"Line {i}" for i in range(8))
    layer = text_layer(many, box=(0.1, 0.45, 0.8, 0.08), overflow="ellipsis", size=0.04)
    img = render(tpl(layer), {}, no_assets)
    left, top, right, bottom = ink_bbox(img)
    # Box is y 0.45..0.53 of 800px = 360..424: the text stays inside it.
    assert top >= 358 and bottom <= 426
    warnings = lint(tpl(layer), {}, no_assets)
    assert any("shortened" in w for w in warnings), warnings
    assert not any("cut off" in w for w in warnings)


def test_fit_warnings_dedupe_and_cap_devices():
    t = tpl(text_layer("Hi", box=(0.0, 0.0, 1.0, 0.05)))
    one = fit_warnings(t, (400, 800), ["iphone-6.7"], "lock")
    many = fit_warnings(t, (400, 800), ["iphone-6.7"] * 20000, "lock")
    assert many == one
    capped = fit_warnings(t, (400, 800), [f"x{i}" for i in range(1000)] + ["iphone-6.7"], "lock")
    assert capped == []  # past the cap of distinct ids, the rest are ignored
