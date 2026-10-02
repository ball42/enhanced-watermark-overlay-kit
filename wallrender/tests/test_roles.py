"""Role variants: one template, different background and wording per role."""

import pytest
from PIL import Image

from wallrender import lint, render, validate
from wallrender.roles import normalize_role, resolve

from test_render import ink_bbox, text_layer, tpl

ROLES = {
    "attribute": "Jamf Setup Role",
    "variants": {
        "nursing": {"background": {"color": "#0B6E4F"}, "values": {"title": "Nursing"}},
        "videoconferencing": {"background": {"asset": "vc"}, "values": {"title": "Video calls"}},
    },
    "empty": {"values": {"title": "Please open the Setup app"}},
    "default": {"values": {"title": "General use"}},
}

ASSETS = {"vc": Image.new("RGB", (40, 80), (200, 0, 0))}.__getitem__


def roled(**extra):
    return tpl(text_layer("{{role.title}}"), roles=ROLES, **extra)


def corner(img):
    return img.getpixel((2, 2))


# --- validation --------------------------------------------------------------


def test_valid_roles_pass():
    assert validate(roled()) == []


@pytest.mark.parametrize(
    "roles, fragment",
    [
        ([], "roles must be an object"),
        ({"variants": {"Bad Key": {}}}, "variant key"),
        ({"variants": {"a": {"values": {"x": 1}}}}, "values must be strings"),
        ({"variants": {"a": {"values": {"Bad-Name": "x"}}}}, "value name"),
        ({"variants": {"a": {"values": {"name": "x"}}}}, "reserved"),
        ({"variants": {"a": {"background": {"color": "red"}}}}, "color"),
        ({"variants": {"a": {"surprise": True}}}, "unknown"),
        ({"attribute": 5}, "attribute"),
        ({"variants": {f"r{i}": {} for i in range(51)}}, "at most 50"),
    ],
)
def test_bad_roles_are_reported(roles, fragment):
    problems = validate(tpl(text_layer("x"), roles=roles))
    assert any(fragment in p for p in problems), problems


def test_variant_color_background_needs_a_canvas():
    t = tpl(text_layer("x"), roles={"default": {"background": {"color": "#000000"}}})
    t.pop("canvas")
    t["background"] = {"asset": "vc"}
    assert any("canvas" in p for p in validate(t))


# --- matching ------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, key",
    [("Video Conferencing", "videoconferencing"), ("  Nursing ", "nursing"), ("", ""), (None, "")],
)
def test_role_values_normalize_like_brander(raw, key):
    assert normalize_role(raw) == key


@pytest.mark.parametrize(
    "role, title",
    [
        ("Nursing", "Nursing"),
        ("Video Conferencing", "Video calls"),
        ("", "Please open the Setup app"),
        (None, "Please open the Setup app"),
        ("Pharmacist", "General use"),
    ],
)
def test_resolve_picks_variant_empty_or_default(role, title):
    values = {} if role is None else {"role": role}
    _, resolved = resolve(roled(), values)
    assert resolved["role"]["title"] == title


def test_role_name_is_the_raw_value():
    _, resolved = resolve(roled(), {"role": "Video Conferencing"})
    assert resolved["role"]["name"] == "Video Conferencing"


def test_a_variant_background_replaces_the_template_background():
    assert corner(render(roled(), {"role": "Nursing"}, ASSETS)) == (0x0B, 0x6E, 0x4F)
    assert corner(render(roled(), {"role": "Video Conferencing"}, ASSETS)) == (200, 0, 0)
    assert corner(render(roled(), {"role": "Other"}, ASSETS)) == (0, 0, 0)  # default keeps it


def test_variant_wording_renders():
    a = render(roled(), {"role": "Nursing"}, ASSETS)
    b = render(roled(), {"role": "Pharmacist"}, ASSETS)
    assert ink_bbox(a) and a.tobytes() != b.tobytes()


def test_no_roles_means_role_is_an_ordinary_value():
    """Without a roles block, nothing about rendering changes."""
    t = tpl(text_layer("{{role}}"))
    assert ink_bbox(render(t, {"role": "Nursing"}, ASSETS))


def test_missing_variant_value_hides_a_hide_if_empty_layer():
    t = tpl(text_layer("{{role.subtitle}}", hide_if_empty=True), roles=ROLES)
    # Pharmacist uses the default variant: black background, no subtitle.
    assert ink_bbox(render(t, {"role": "Pharmacist"}, ASSETS)) is None


def test_lint_names_the_variant_used():
    warnings = lint(roled(), {"role": "Pharmacist"}, ASSETS)
    assert any("role 'Pharmacist'" in w and "default" in w for w in warnings), warnings


def test_stress_values_send_a_long_role_string():
    from wallrender.cli import stress_values

    values = stress_values(roled())
    assert isinstance(values["role"], str) and len(values["role"]) > 40


def test_stress_renders_each_role_variant(tmp_path, capsys):
    import json

    from wallrender.cli import main

    t = tmp_path / "t.json"
    t.write_text(json.dumps(roled()))
    v = tmp_path / "v.json"
    v.write_text("{}")
    out = tmp_path / "out.png"
    main(["preview", str(t), str(v), "-o", str(out), "--stress", "--assets", str(tmp_path)])
    names = {p.name for p in tmp_path.iterdir()}
    assert "out-role-nursing.png" in names
