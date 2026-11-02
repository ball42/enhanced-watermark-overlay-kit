"""Both pages are on the shared roster design system: the vendored roster CSS
loads before EWOK's own, and EWOK's colour, shadow and font variables are
roster tokens, apart from the Endor navbar accent."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "static" / "css" / "vendor"
CSS = ROOT / "static" / "css"
ROSTER_CSS = ("/static/css/vendor/roster-web.css", "/static/css/vendor/roster-html.css")
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


@pytest.mark.parametrize("name", ["roster-web.css", "roster-html.css"])
def test_vendored_files_carry_their_version_stamp(name):
    first = (VENDOR / name).read_text(encoding="utf-8").splitlines()[0]
    assert re.search(r"roster-bridge \S+ from @blakesteve/roster \S+ " + re.escape(name) + " sha256:", first)


def test_vendored_files_keep_the_licence_notice():
    text = (VENDOR / "README.md").read_text(encoding="utf-8")
    assert "MIT" in text and "@blakesteve/roster" in text
    assert "Copyright (c) 2026 Blake Ball." in text


@pytest.mark.parametrize("path", ["/", "/template"])
def test_pages_load_roster_before_their_own_css(client, path):
    body = client.get(path).get_data(as_text=True)
    at = [body.index(href) for href in ROSTER_CSS]
    assert at == sorted(at)
    assert at[-1] < body.index("/static/css/style.css")
    assert "fonts.googleapis.com" not in body  # roster's font stacks replace Inter


@pytest.mark.parametrize("path", ["/", "/template"])
def test_panels_are_roster_cards(client, path):
    body = client.get(path).get_data(as_text=True)
    assert 'class="rb-card section-container' in body
    assert "section-container" not in body.replace("rb-card section-container", "")


@pytest.mark.parametrize("name", ["style.css", "template.css"])
def test_no_private_palette(name):
    css = (CSS / name).read_text(encoding="utf-8")
    found = HEX.findall(css)
    if name == "style.css":
        assert found == ["#2f4a33"]  # the Endor navbar, EWOK's one accent
    else:
        assert found == []
    assert "rgba(" not in css
    assert not re.search(r":\s*white\b|solid white\b", css)


def test_colour_shadow_and_font_variables_are_roster_tokens():
    css = (CSS / "style.css").read_text(encoding="utf-8")
    root = re.search(r":root \{(.*?)\n\}", css, re.S).group(1)
    decls = dict(re.findall(r"(--(?:color|shadow|font|ewok)-[\w-]+):\s*([^;]+);", root))
    assert decls, "no variables found"
    for name, value in decls.items():
        if name == "--color-navbar":
            continue
        assert re.search(r"var\(--(roster|rb)-", value), f"{name}: {value}"


def test_status_and_warning_markup_use_roster_classes():
    app = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    tpl = (ROOT / "static" / "js" / "template.js").read_text(encoding="utf-8")
    assert "'rb-alert '" in app
    assert "'rb-alert rb-alert--warn'" in tpl and "'rb-alert rb-alert--ok ok'" in tpl
    assert "rb-badge--warn" in tpl
