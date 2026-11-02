"""Both pages in a browser: they follow the OS theme, the navbar toggle
switches and saves it, and in dark the preview frame is a dark checkerboard."""

import pytest

BG = "getComputedStyle(document.body).backgroundColor"
FRAME = "getComputedStyle(document.querySelector('.tpl-preview-frame')).backgroundImage"


def rgb(value):
    return [int(n) for n in value[value.index("(") + 1:value.index(")")].split(",")[:3]]


def luminance(value):
    r, g, b = rgb(value)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


@pytest.mark.parametrize("path", ["/", "/template"])
def test_pages_follow_the_os_setting(page, path):
    page.emulate_media(color_scheme="dark")
    page.goto(path)
    assert page.evaluate("document.documentElement.classList.contains('dark')")
    assert luminance(page.evaluate(BG)) < 40
    assert page.get_attribute("[data-roster-theme-toggle]", "aria-pressed") == "true"
    page.emulate_media(color_scheme="light")
    page.goto(path)
    assert not page.evaluate("document.documentElement.classList.contains('dark')")
    assert luminance(page.evaluate(BG)) > 200


def test_the_toggle_switches_and_remembers_the_theme(page):
    page.emulate_media(color_scheme="light")
    page.goto("/template")
    page.click("[data-roster-theme-toggle]")
    assert page.evaluate("document.documentElement.classList.contains('dark')")
    assert page.get_attribute("[data-roster-theme-toggle]", "aria-pressed") == "true"
    assert page.evaluate("localStorage.getItem('roster-theme')") == "dark"
    page.goto("/")
    assert page.evaluate("document.documentElement.classList.contains('dark')")


def test_dark_preview_frame_is_a_dark_checkerboard(page):
    page.emulate_media(color_scheme="dark")
    page.goto("/template")
    frame = page.evaluate(FRAME)
    assert "conic-gradient" in frame
    colours = [c + ")" for c in frame.split(")") if "rgb" in c]
    assert colours and all(luminance(c[c.index("rgb"):]) < 60 for c in colours), frame
