"""Panel layers: a translucent, rounded backdrop behind other layers."""

import pytest

from wallrender import lint, render, validate

BASE = {"schema_version": 1, "canvas": {"width": 200, "height": 100},
        "background": {"color": "#FFFFFF"}}


def no_assets(asset_id):
    raise KeyError(asset_id)


def with_layers(*layers):
    return dict(BASE, layers=list(layers))


def panel(**extra):
    return dict({"type": "panel", "box": {"x": 0.1, "y": 0.2, "w": 0.8, "h": 0.6},
                 "color": "#0B2545"}, **extra)


def test_an_opaque_panel_fills_its_box():
    img = render(with_layers(panel()), {}, no_assets)
    assert img.getpixel((100, 50)) == (0x0B, 0x25, 0x45)
    assert img.getpixel((10, 10)) == (255, 255, 255)  # outside the box


def test_opacity_blends_with_what_is_behind():
    r, g, b = render(with_layers(panel(opacity=0.5)), {}, no_assets).getpixel((100, 50))
    assert (r, g, b) == (pytest.approx(133, abs=1), pytest.approx(146, abs=1), pytest.approx(162, abs=1))


def test_color_alpha_and_opacity_multiply():
    a = render(with_layers(panel(color="#0B254580", opacity=1)), {}, no_assets).getpixel((100, 50))
    b = render(with_layers(panel(color="#0B2545", opacity=0.5)), {}, no_assets).getpixel((100, 50))
    c = render(with_layers(panel(color="#0B254580", opacity=0.5)), {}, no_assets).getpixel((100, 50))
    assert a == pytest.approx(b, abs=1)
    assert c[0] > a[0]  # a quarter as opaque: lighter


def test_radius_rounds_the_corners():
    square = render(with_layers(panel()), {}, no_assets)
    round_ = render(with_layers(panel(radius=0.5)), {}, no_assets)
    assert square.getpixel((21, 21)) == (0x0B, 0x25, 0x45)
    assert round_.getpixel((21, 21)) == (255, 255, 255)  # the corner is cut away
    assert round_.getpixel((100, 50)) == (0x0B, 0x25, 0x45)


def test_zero_opacity_draws_nothing():
    assert render(with_layers(panel(opacity=0)), {}, no_assets).getpixel((100, 50)) == (255, 255, 255)


def test_a_panel_makes_white_text_pass_the_contrast_check():
    text = {"type": "text", "text": "Front Desk", "size": 0.2, "color": "#FFFFFF",
            "box": {"x": 0.1, "y": 0.2, "w": 0.8, "h": 0.6}}
    assert any("contrast" in w for w in lint(with_layers(text), {}, no_assets))
    assert not any("contrast" in w for w in lint(with_layers(panel(), text), {}, no_assets))


@pytest.mark.parametrize("extra, problem", [
    ({"opacity": 1.5}, "opacity"), ({"opacity": -0.1}, "opacity"), ({"opacity": True}, "opacity"),
    ({"opacity": "0.5"}, "opacity"), ({"radius": 0.6}, "radius"), ({"radius": -1}, "radius"),
    ({"radius": float("nan")}, "radius"), ({"color": "navy"}, "color"),
])
def test_bad_panels_are_refused(extra, problem):
    problems = validate(with_layers(panel(**extra)))
    assert any(problem in p for p in problems)


def test_a_one_pixel_panel_renders():
    tiny = panel(box={"x": 0, "y": 0, "w": 0.001, "h": 0.001}, radius=0.5)
    assert render(with_layers(tiny), {}, no_assets).size == (200, 100)
