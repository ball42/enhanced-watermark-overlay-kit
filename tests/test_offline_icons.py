"""Icons are vendored: no page links to a CDN, and every Font Awesome name EWOK
uses exists in the vendored copy."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FA = ROOT / "static" / "vendor" / "fontawesome"
SOURCES = [*(ROOT / "templates").glob("*.html"), *(ROOT / "static" / "js").glob("*.js")]
# fa-solid etc. are style classes, not icon names.
STYLE_CLASSES = {"fa-solid", "fa-regular", "fa-brands", "fa-fw", "fa-spin"}


@pytest.mark.parametrize("path", ["/", "/template"])
def test_pages_load_nothing_from_outside(client, path):
    body = client.get(path).get_data(as_text=True)
    assert not re.search(r"""(?:src|href)=["']?(?:https?:)?//""", body)
    assert "/static/vendor/fontawesome/css/solid.min.css" in body


def test_every_icon_name_used_is_in_the_vendored_font():
    css = (FA / "css" / "fontawesome.min.css").read_text(encoding="utf-8")
    defined = set(re.findall(r"\.(fa-[a-z0-9-]+):before", css))
    used = set()
    for source in SOURCES:
        used |= set(re.findall(r"\bfa-[a-z0-9]+(?:-[a-z0-9]+)*\b", source.read_text(encoding="utf-8")))
    missing = sorted(used - defined - STYLE_CLASSES)
    assert not missing, f"not in the vendored Font Awesome: {missing}"


def test_the_vendored_font_files_are_there_and_licensed():
    solid = (FA / "css" / "solid.min.css").read_text(encoding="utf-8")
    for font in re.findall(r"url\(\.\./webfonts/([^)]+)\)", solid):
        assert (FA / "webfonts" / font).is_file(), font
    assert "Font Awesome Free 6.0.0" in solid
    assert "CC BY 4.0" in (FA / "README.md").read_text(encoding="utf-8")
    assert (FA / "LICENSE.txt").is_file()
