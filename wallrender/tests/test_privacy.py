"""Person fields (user.*) are opt-in per template and never go in a QR code.
JAWA ADR-0013: what a lock screen may show."""

import pytest

from wallrender import validate

from test_render import text_layer, tpl

QR = {"type": "qr", "box": {"x": 0.3, "y": 0.6, "w": 0.4, "h": 0.2}}


def test_person_fields_flag_must_be_a_boolean():
    assert validate(tpl(text_layer("x"), person_fields=True)) == []
    assert validate(tpl(text_layer("x"), person_fields=False)) == []
    assert any("person_fields" in p for p in validate(tpl(text_layer("x"), person_fields="yes")))


@pytest.mark.parametrize("text", ["{{user.real_name}}", "Hi {{ user.email }}", "{{user.username}}"])
def test_user_fields_in_text_need_the_template_to_opt_in(text):
    assert any("person_fields" in p for p in validate(tpl(text_layer(text))))
    assert validate(tpl(text_layer(text), person_fields=True)) == []


@pytest.mark.parametrize("opt_in", [False, True])
def test_user_fields_never_go_in_a_qr_code(opt_in):
    t = tpl({**QR, "data": "mailto:{{user.email}}"}, person_fields=opt_in)
    assert any("QR" in p and "user" in p for p in validate(t))


def test_role_variant_text_is_not_affected():
    t = tpl(text_layer("{{role.title}}"), roles={"default": {"values": {"title": "x"}}})
    assert validate(t) == []
