"""The wallrender release a template needs, and unknown layer fields."""

from wallrender import required_version, validate
from wallrender.schema import features_used

BASE = {"schema_version": 1, "canvas": {"width": 400, "height": 800}, "background": {"color": "#000000"}}
TEXT = {"type": "text", "text": "Front Desk", "box": {"x": 0.1, "y": 0.5, "w": 0.8, "h": 0.1}, "size": 0.05}
PANEL = {"type": "panel", "box": {"x": 0.05, "y": 0.45, "w": 0.9, "h": 0.2}, "opacity": 0.5}


def tpl(*layers, **extra):
    return {**BASE, "layers": list(layers), **extra}


def test_a_plain_template_needs_the_first_release():
    assert required_version(tpl(TEXT)) == "0.1.0"


def test_bold_and_semibold_need_0_12_0():
    for weight in ("bold", "semibold", "medium"):
        assert required_version(tpl({**TEXT, "weight": weight})) == "0.12.0"


def test_regular_weight_does_not_raise_the_version():
    assert required_version(tpl({**TEXT, "weight": "regular"})) == "0.1.0"


def test_a_panel_needs_0_9_0():
    assert required_version(tpl(PANEL, TEXT)) == "0.9.0"


def test_the_highest_feature_wins_and_each_feature_is_named():
    template = tpl(PANEL, {**TEXT, "weight": "bold"}, screen="home")
    assert required_version(template) == "0.12.0"
    assert ("0.12.0", "layer 1: weight 'bold'") in features_used(template)
    assert ("0.9.0", "layer 0: panel layer") in features_used(template)
    assert ("0.8.0", "screen") in features_used(template)


def test_an_unknown_layer_field_is_a_problem():
    problems = validate(tpl({**TEXT, "shadow": True}))
    assert problems == ["layer 0: unknown fields ['shadow']"]


def test_a_field_of_another_layer_type_is_a_problem():
    problems = validate(tpl({**PANEL, "weight": "bold"}))
    assert problems == ["layer 0: unknown fields ['weight']"]


def test_every_known_field_still_validates():
    text = {**TEXT, "color": "#FFFFFF", "align": "left", "font": "noto-sans", "weight": "bold",
            "overflow": "ellipsis", "min_size": 0.02, "hide_if_empty": True}
    qr = {"type": "qr", "data": "x", "box": {"x": 0.3, "y": 0.1, "w": 0.2, "h": 0.1},
          "color": "#000000", "background": "#FFFFFF", "hide_if_empty": True}
    image = {"type": "image", "asset": "logo", "box": {"x": 0.3, "y": 0.7, "w": 0.2, "h": 0.1}}
    panel = {**PANEL, "color": "#000000", "radius": 0.1}
    assert validate(tpl(text, qr, image, panel)) == []
