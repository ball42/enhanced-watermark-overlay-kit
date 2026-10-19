"""Text weight: Regular to Bold from the bundled variable Noto Sans."""

import hashlib

import pytest

from wallrender import render, validate

BLACK_BG = {"schema_version": 1, "canvas": {"width": 400, "height": 800}, "background": {"color": "#000000"}}
TEXT = {"type": "text", "text": "Front Desk iPad 7", "box": {"x": 0.1, "y": 0.5, "w": 0.8, "h": 0.1},
        "size": 0.05, "color": "#FFFFFF", "align": "center"}
# sha256 of TEXT's pixels from wallrender 0.11.0 (no weight property), Pillow 11.3.
REGULAR_SHA = "9768ebf9b83785bef43a3ec068ff5c68bbe664e11ff3b021576ffb05ad54f79b"


def tpl(**layer):
    return {**BLACK_BG, "layers": [{**TEXT, **layer}]}


def no_assets(asset_id):
    raise KeyError(asset_id)


def ink(img):
    return sum(1 for v in img.convert("L").getdata() if v > 127)


def test_a_layer_with_no_weight_renders_as_before():
    img = render(tpl(), {}, no_assets)
    assert hashlib.sha256(img.tobytes()).hexdigest() == REGULAR_SHA


def test_regular_is_the_default_weight():
    assert render(tpl(weight="regular"), {}, no_assets).tobytes() == render(tpl(), {}, no_assets).tobytes()


def test_bold_draws_more_ink_than_regular():
    regular = ink(render(tpl(), {}, no_assets))
    medium = ink(render(tpl(weight="medium"), {}, no_assets))
    semibold = ink(render(tpl(weight="semibold"), {}, no_assets))
    bold = ink(render(tpl(weight="bold"), {}, no_assets))
    assert regular < medium < semibold < bold


@pytest.mark.parametrize("weight", ["regular", "medium", "semibold", "bold"])
def test_the_four_weights_are_valid(weight):
    assert validate(tpl(weight=weight)) == []


@pytest.mark.parametrize("weight", ["heavy", "Bold", 700, None, ""])
def test_other_weights_are_rejected(weight):
    problems = validate(tpl(weight=weight))
    assert any("weight must be one of" in p for p in problems), problems
