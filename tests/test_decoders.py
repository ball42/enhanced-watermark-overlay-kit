"""Pillow only runs the decoders EWOK names: the photo editor's PHOTO_FORMATS
and the template designer's FORMATS. Every Image.open() in views/ and utils/
passes one of those lists, and CLAUDE.md names both, so the next Pillow
advisory is read against the right list."""

import ast
import pathlib
import re

import config
from views import template_api

ROOT = pathlib.Path(__file__).resolve().parent.parent
LISTS = {"PHOTO_FORMATS", "FORMATS"}


def _list_name(node):
    # formats=PHOTO_FORMATS, formats=tuple(FORMATS) or formats=config.PHOTO_FORMATS
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "tuple" and node.args:
        node = node.args[0]
    if isinstance(node, ast.Attribute):
        return node.attr
    return node.id if isinstance(node, ast.Name) else None


def image_opens():
    for folder in ("views", "utils"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(), str(path))):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "open" and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "Image"):
                    yield f"{path.relative_to(ROOT)}:{node.lineno}", node


def test_every_image_open_names_its_decoders():
    found = list(image_opens())
    assert len(found) >= 6
    for where, call in found:
        formats = [kw.value for kw in call.keywords if kw.arg == "formats"]
        assert formats, f"{where}: Image.open() without formats="
        assert _list_name(formats[0]) in LISTS, f"{where}: formats= is not PHOTO_FORMATS or FORMATS"


def test_claude_md_names_both_decoder_lists():
    text = (ROOT / "CLAUDE.md").read_text()
    rule = next(line for line in text.splitlines() if "formats=" in line and "Image.open()" in line)
    assert "only PNG and JPEG decoders ever run" not in rule
    for fmt in set(config.PHOTO_FORMATS) | set(template_api.FORMATS):
        assert re.search(rf"\b{fmt}\b", rule), f"CLAUDE.md's decoder rule doesn't name {fmt}"
