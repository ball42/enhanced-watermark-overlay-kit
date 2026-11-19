"""Template designer in a browser: the selected box and the focus ring stand
out on a white wallpaper and on a black one (3:1, WCAG 1.4.11)."""

import io
import json

import pytest
from PIL import Image


def luminance(rgb):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def template(color):
    return {
        "schema_version": 1, "name": "Ring", "canvas": {"width": 1290, "height": 2796},
        "background": {"color": color},
        "layers": [{"type": "text", "text": "Hi", "box": {"x": 0.3, "y": 0.4, "w": 0.4, "h": 0.1},
                    "size": 0.03, "color": "#888888", "align": "center"}],
    }


def best_edge_contrast(page, band=range(-10, 3)):
    """The strongest contrast between the canvas and any pixel just left of
    the first box, across the band the border, outline and ring are drawn in."""
    box = page.evaluate("""() => {
        const b = document.querySelector('#overlay .tpl-boxframe[data-index="0"]').getBoundingClientRect();
        return {x: Math.round(b.left), y: Math.round(b.top + b.height / 2)};
    }""")
    shot = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    canvas = shot.getpixel((box["x"] - 20, box["y"]))
    ring = [shot.getpixel((box["x"] + dx, box["y"])) for dx in band]
    return canvas, max(ratio(canvas, px) for px in ring)


@pytest.mark.parametrize("color", ["#FFFFFF", "#000000"])
@pytest.mark.parametrize("theme", ["light", "dark"])
def test_selected_and_focused_boxes_keep_3_to_1(page, color, theme):
    page.add_init_script(f"localStorage.setItem('ewok-template-draft', {json.dumps(json.dumps(template(color)))});"
                         f"localStorage.setItem('roster-theme', '{theme}');")
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    frame = '#overlay .tpl-boxframe[data-index="0"]'
    page.wait_for_selector(f"{frame}.selected")
    page.mouse.move(0, 0)
    canvas, best = best_edge_contrast(page)
    assert canvas == tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
    assert best >= 3, f"selected box edge is {best:.2f}:1 on {color}"
    # Keyboard focus: Tab until the box has it, so :focus-visible applies.
    for _ in range(200):
        page.keyboard.press("Tab")
        if page.evaluate(f"document.activeElement === document.querySelector('{frame}')"):
            break
    assert page.evaluate(f"document.querySelector('{frame}').matches(':focus-visible')")
    # Outside the border only: the ring itself, not the blue border it wraps.
    canvas, best = best_edge_contrast(page, range(-10, 0))
    assert best >= 3, f"focus ring is {best:.2f}:1 on {color}"
