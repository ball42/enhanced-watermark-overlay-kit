"""Template designer in a browser: the layer tag does not cover the text it marks."""

import json


def rects(page, i):
    return page.evaluate(f"""() => {{
        const f = document.querySelector('#overlay .tpl-boxframe[data-index="{i}"]');
        const r = (el) => {{ const b = el.getBoundingClientRect(); return {{top: b.top, bottom: b.bottom}}; }};
        // inner: where the box's content starts, inside its border.
        return {{frame: r(f), inner: r(f).top + f.clientTop, tag: r(f.querySelector('.tpl-boxlabel'))}};
    }}""")


def test_the_tag_sits_above_the_box(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    r = rects(page, 0)
    assert r["tag"]["bottom"] <= r["inner"]  # over the border at most, never the text
    label = '#overlay .tpl-boxframe[data-index="0"] .tpl-boxlabel'
    assert page.inner_text(label) == "1"
    assert page.evaluate(f"getComputedStyle(document.querySelector('{label}'), '::after').content") == '" editing"'


def test_a_box_at_the_top_edge_keeps_its_tag_inside(page):
    top = {
        "schema_version": 1, "name": "Top", "canvas": {"width": 1290, "height": 2796},
        "background": {"color": "#0B2545"},
        "layers": [{"type": "text", "text": "{{device_name}}", "box": {"x": 0.1, "y": 0.0, "w": 0.8, "h": 0.05},
                    "size": 0.028, "color": "#FFFFFF", "align": "center"}],
    }
    page.add_init_script(f"localStorage.setItem('ewok-template-draft', {json.dumps(json.dumps(top))});")
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    r = rects(page, 0)
    assert r["tag"]["top"] >= r["frame"]["top"] - 1
    # Dragged or typed down off the edge, the tag moves back above the box.
    page.fill('[data-box="y"]', "0.3")
    r = rects(page, 0)
    assert r["tag"]["bottom"] <= r["inner"]
