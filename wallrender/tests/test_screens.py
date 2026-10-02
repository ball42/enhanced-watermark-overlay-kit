"""Milestone 4: a template may say which screen it is for."""

import pytest

from wallrender import validate

from test_render import text_layer, tpl


@pytest.mark.parametrize("screen", ["lock", "home", "both"])
def test_screen_values(screen):
    assert validate(tpl(text_layer("x"), screen=screen)) == []


@pytest.mark.parametrize("screen", ["Lock", "all", 1, None])
def test_bad_screen_values(screen):
    assert any("screen" in p for p in validate(tpl(text_layer("x"), screen=screen)))


def test_screen_is_optional():
    assert validate(tpl(text_layer("x"))) == []
