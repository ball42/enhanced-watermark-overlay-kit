"""Device profiles: how iOS crops a wallpaper and what covers it."""

import pytest

from wallrender.devices import device_profiles, fit_warnings, visible_region, zones_on_canvas

from test_render import text_layer, tpl


def profile(pid):
    return next(p for p in device_profiles() if p["id"] == pid)


def test_profiles_are_well_formed():
    profiles = device_profiles()
    assert {"iphone", "ipad"} == {p["family"] for p in profiles}
    for p in profiles:
        w, h = p["screen"]
        assert 0 < w < h, p["id"]  # portrait
        for screen in ("lock", "home"):
            for orientation in ("portrait", "landscape") if p["rotates"] else ("portrait",):
                for zone in p["zones"][orientation][screen]:
                    x0, y0, x1, y1 = zone["box"]
                    assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1, (p["id"], zone)
                    assert zone["label"]


def test_cover_crop_of_a_tall_canvas_on_a_wide_screen():
    """The on-device bug: a 1290x2796 template on a 2048x2732 iPad keeps only
    the middle ~62% of its height."""
    x0, y0, x1, y1 = visible_region((1290, 2796), (2048, 2732))
    assert (x0, x1) == (0, 1)
    assert y1 - y0 == pytest.approx(0.615, abs=0.005)
    assert y0 == pytest.approx((1 - (y1 - y0)) / 2)


def test_square_canvas_keeps_the_centre_in_both_orientations():
    portrait = visible_region((2732, 2732), (2048, 2732))
    landscape = visible_region((2732, 2732), (2732, 2048))
    assert portrait[1] == 0 and portrait[3] == 1
    assert landscape[0] == 0 and landscape[2] == 1
    assert portrait[0] == pytest.approx(0.125, abs=0.001)


def test_same_aspect_shows_everything():
    assert visible_region((1290, 2796), (1290, 2796)) == (0, 0, 1, 1)


def test_zones_map_into_canvas_fractions():
    z = zones_on_canvas(profile("ipad-12.9"), "portrait", "lock", (2732, 2732))
    clock = next(b for label, b in z if label == "Clock")
    # Portrait shows x 0.125..0.875 of the square canvas; zones live inside it.
    assert clock[0] >= 0.125 - 1e-9 and clock[2] <= 0.875 + 1e-9


def test_a_qr_cut_off_on_ipad_is_reported():
    qr = {"type": "qr", "data": "x", "box": {"x": 0.35, "y": 0.76, "w": 0.3, "h": 0.14}}
    t = tpl(qr, canvas={"width": 1290, "height": 2796})
    warnings = fit_warnings(t, (1290, 2796), ["ipad-12.9"], "lock")
    assert any("layer 0" in w and "cut off" in w and "iPad" in w for w in warnings), warnings


def test_text_under_the_clock_is_reported():
    top = text_layer("Hi", box=(0.1, 0.08, 0.8, 0.06))
    t = tpl(top, canvas={"width": 1290, "height": 2796})
    warnings = fit_warnings(t, (1290, 2796), ["iphone-6.7"], "lock")
    assert any("layer 0" in w and "Clock" in w for w in warnings), warnings


def test_a_layout_that_fits_is_quiet():
    mid = text_layer("Hi", box=(0.32, 0.45, 0.36, 0.05))  # inside the iPhone strip of a square
    t = tpl(mid, canvas={"width": 2732, "height": 2732})
    assert fit_warnings(t, (2732, 2732), ["ipad-12.9", "iphone-6.7"], "lock") == []


def test_unknown_device_ids_are_ignored():
    t = tpl(text_layer("Hi"))
    assert fit_warnings(t, (400, 800), ["nope"], "lock") == []
