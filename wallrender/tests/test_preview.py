"""Designer feedback: lint warnings and the `wallrender preview` command."""

import json

import pytest
from PIL import Image

from wallrender import lint
from wallrender.cli import main
from wallrender.render import contrast_ratio

from test_render import no_assets, text_layer, tpl


# --- lint: overflow ----------------------------------------------------------


def test_text_that_fits_gets_no_overflow_warning():
    assert lint(tpl(text_layer("Hi")), {}, no_assets) == []


def test_text_shrunk_a_lot_to_fit_is_reported():
    warnings = lint(tpl(text_layer("{{name}}")), {"name": "W" * 25}, no_assets)
    assert any("layer 0: text shrank from" in w for w in warnings), warnings


def test_text_that_cannot_fit_even_at_the_minimum_is_reported():
    narrow = text_layer("{{name}}", box=(0.45, 0.5, 0.02, 0.01))
    warnings = lint(tpl(narrow), {"name": "W" * 200}, no_assets)
    assert any("layer 0: text does not fit" in w for w in warnings), warnings


# --- lint: contrast ----------------------------------------------------------


def test_contrast_ratio_matches_wcag():
    assert contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)
    assert contrast_ratio((119, 119, 119), (255, 255, 255)) == pytest.approx(
        4.48, abs=0.01
    )


def test_low_contrast_text_is_reported():
    dim = text_layer("Hello", color="#222222")
    warnings = lint(tpl(dim), {}, no_assets)
    assert any("layer 0: low contrast" in w for w in warnings), warnings


def test_contrast_is_measured_against_what_is_behind_the_box():
    """White text on a white panel drawn by an earlier layer is unreadable,
    even though the canvas background is black."""
    panel = Image.new("RGB", (40, 40), "white")
    template = tpl(
        {"type": "image", "asset": "panel", "box": {"x": 0, "y": 0.4, "w": 1, "h": 0.3}},
        text_layer("Hello"),
    )
    assets = {"panel": panel}.__getitem__
    warnings = lint(template, {}, assets)
    assert any("layer 1: low contrast" in w for w in warnings), warnings


def test_good_contrast_is_quiet():
    assert not any("contrast" in w for w in lint(tpl(text_layer("Hi")), {}, no_assets))


# --- the CLI -----------------------------------------------------------------


@pytest.fixture()
def files(tmp_path):
    def write(template, values=None):
        t = tmp_path / "t.json"
        t.write_text(json.dumps(template))
        v = tmp_path / "v.json"
        v.write_text(json.dumps(values or {}))
        return str(t), str(v), str(tmp_path / "out.png")

    return write


def test_preview_writes_the_png(files, capsys):
    t, v, out = files(tpl(text_layer("{{name}}")), {"name": "iPad"})
    assert main(["preview", t, v, "-o", out]) == 0
    with Image.open(out) as img:
        assert img.size == (400, 800)
    assert "wrote" in capsys.readouterr().out


def test_preview_prints_warnings_but_still_writes(files, capsys):
    t, v, out = files(tpl(text_layer("{{name}}")), {})
    assert main(["preview", t, v, "-o", out]) == 0
    err = capsys.readouterr().err
    assert "no value for {{name}}" in err
    with Image.open(out):
        pass


def test_strict_fails_on_warnings(files):
    t, v, out = files(tpl(text_layer("{{name}}")), {})
    assert main(["preview", t, v, "-o", out, "--strict"]) == 3


def test_invalid_template_exits_1_and_writes_nothing(files, capsys):
    t, v, out = files({"schema_version": 99}, {})
    assert main(["preview", t, v, "-o", out]) == 1
    assert "schema_version" in capsys.readouterr().err
    with pytest.raises(FileNotFoundError):
        open(out)


def test_unreadable_values_file_exits_1(files, tmp_path, capsys):
    t, _, out = files(tpl(text_layer("x")))
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    assert main(["preview", t, str(bad), "-o", out]) == 1
    assert "bad.json" in capsys.readouterr().err


def test_assets_load_from_the_template_folder_by_default(files, tmp_path):
    Image.new("RGB", (50, 50), "red").save(tmp_path / "logo.png")
    template = tpl({"type": "image", "asset": "logo", "box": {"x": 0, "y": 0, "w": 1, "h": 1}})
    t, v, out = files(template)
    assert main(["preview", t, v, "-o", out]) == 0
    with Image.open(out) as img:
        assert img.getpixel((200, 400)) == (255, 0, 0)


def test_assets_option_and_containment(files, tmp_path):
    elsewhere = tmp_path / "art"
    elsewhere.mkdir()
    Image.new("RGB", (50, 50), "blue").save(elsewhere / "logo.png")
    template = tpl({"type": "image", "asset": "logo", "box": {"x": 0, "y": 0, "w": 1, "h": 1}})
    t, v, out = files(template)
    assert main(["preview", t, v, "-o", out, "--assets", str(elsewhere)]) == 0
    with Image.open(out) as img:
        assert img.getpixel((200, 400)) == (0, 0, 255)


def test_missing_asset_exits_1(files, capsys):
    template = tpl({"type": "image", "asset": "nope", "box": {"x": 0, "y": 0, "w": 1, "h": 1}})
    t, v, out = files(template)
    assert main(["preview", t, v, "-o", out]) == 1
    assert "nope" in capsys.readouterr().err


def test_shipped_example_previews_cleanly(tmp_path):
    import os

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = str(tmp_path / "ex.png")
    code = main([
        "preview",
        os.path.join(here, "examples", "brander-basic.json"),
        os.path.join(here, "examples", "sample-device.json"),
        "-o", out, "--strict",
    ])
    assert code == 0
