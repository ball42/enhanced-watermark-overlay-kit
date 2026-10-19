"""The shipped examples pass wallrender's own checks on the device they are made for."""
import json
from pathlib import Path

from wallrender.cli import main
from wallrender.devices import fit_warnings

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _load(name):
    return json.loads((EXAMPLES / name).read_text())


def test_brander_basic_clears_every_iphone_lock_zone():
    template = _load("brander-basic.json")
    canvas = (template["canvas"]["width"], template["canvas"]["height"])
    assert fit_warnings(template, canvas, ["iphone-6.7", "iphone-6.1", "iphone-se"], "lock") == []


def test_brander_basic_previews_strict_on_iphone_67(tmp_path, capsys):
    code = main(["preview", str(EXAMPLES / "brander-basic.json"),
                 str(EXAMPLES / "sample-device.json"),
                 "-o", str(tmp_path / "out.png"), "--devices", "iphone-6.7", "--strict"])
    assert code == 0, capsys.readouterr().err
