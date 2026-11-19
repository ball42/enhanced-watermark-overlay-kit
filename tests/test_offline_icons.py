"""Icons are vendored: no page links to a CDN, every Font Awesome name EWOK
uses exists in the vendored subset, and the subset holds only those."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FA = ROOT / "static" / "vendor" / "fontawesome"
FULL = ROOT / "vendor" / "fontawesome"
ICONS_BUDGET = 40_000  # bytes of icon CSS and font together; all of Font Awesome was 195,772
SOURCES = [*(ROOT / "templates").glob("*.html"), *(ROOT / "static" / "js").glob("*.js")]
# fa-solid etc. are style classes, not icon names.
STYLE_CLASSES = {"fa-solid", "fa-regular", "fa-brands", "fa-fw", "fa-spin"}


@pytest.mark.parametrize("path", ["/", "/template"])
def test_pages_load_nothing_from_outside(client, path):
    body = client.get(path).get_data(as_text=True)
    assert not re.search(r"""(?:src|href)=["']?(?:https?:)?//""", body)
    assert "/static/vendor/fontawesome/css/icons.min.css?v=" in body
    assert "fontawesome.min.css" not in body and "solid.min.css" not in body


def used_names():
    used = set()
    for source in SOURCES:
        used |= set(re.findall(r"\bfa-[a-z0-9]+(?:-[a-z0-9]+)*\b", source.read_text(encoding="utf-8")))
    return used - STYLE_CLASSES


def defined(css_path):
    return set(re.findall(r"\.(fa-[a-z0-9-]+):before", css_path.read_text(encoding="utf-8")))


def test_every_icon_name_used_is_in_the_vendored_font():
    missing = sorted(used_names() - defined(FA / "css" / "icons.min.css"))
    assert not missing, f"not in the icon subset (run scripts/subset_icons.py): {missing}"
    assert not used_names() - defined(FULL / "css" / "fontawesome.min.css")


def test_the_subset_holds_only_the_icons_in_use():
    extra = sorted(defined(FA / "css" / "icons.min.css") - used_names())
    assert not extra, f"no longer used; run scripts/subset_icons.py: {extra}"


def test_the_icon_css_and_font_stay_small():
    css = FA / "css" / "icons.min.css"
    fonts = [FA / "webfonts" / f.split("?")[0]
             for f in re.findall(r"url\(\.\./webfonts/([^)]+)\)", css.read_text(encoding="utf-8"))]
    assert fonts and all(f.suffix == ".woff2" for f in fonts)
    total = css.stat().st_size + sum(f.stat().st_size for f in fonts)
    assert total < ICONS_BUDGET, f"{total:,} bytes"


def test_the_vendored_font_files_are_there_and_licensed():
    css = (FA / "css" / "icons.min.css").read_text(encoding="utf-8")
    for font in re.findall(r"url\(\.\./webfonts/([^)?]+)", css):
        assert (FA / "webfonts" / font).is_file(), font
    assert "Font Awesome Free 6.0.0" in css
    for folder in (FA, FULL):
        assert "CC BY 4.0" in (folder / "README.md").read_text(encoding="utf-8")
        assert (folder / "LICENSE.txt").is_file()


def test_the_full_copy_is_not_served(client):
    assert client.get("/static/vendor/fontawesome/css/fontawesome.min.css").status_code == 404
