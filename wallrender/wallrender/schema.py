"""Template schema v1: validation only, no rendering.

A template is untrusted input (it is uploaded to the JAWA server), so every
field is checked and bounded before anything is drawn."""

from __future__ import annotations

import re
from typing import Any

SCHEMA_VERSION = 1
MAX_SIDE = 8192
MAX_PIXELS = 40_000_000
MAX_LAYERS = 50
MAX_TEXT = 500
MAX_QR = 512
MAX_TEXT_SIZE = 0.5  # font size as a fraction of canvas height
FONTS = {"noto-sans"}
ALIGNS = {"left", "center", "right"}

ASSET_ID = re.compile(r"^[a-z0-9_-]{1,64}$")
COLOR = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")
PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}")
VARIABLE_PATH = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)*$")


class TemplateError(ValueError):
    """The template failed validation; .problems lists why."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def variables_in(text: str) -> list[str]:
    return [m.strip() for m in PLACEHOLDER.findall(text)]


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_box(where: str, box: Any, problems: list[str]) -> None:
    if not isinstance(box, dict) or not all(_number(box.get(k)) for k in "xywh"):
        problems.append(f"{where}: box needs numeric x, y, w, h (fractions of the canvas)")
        return
    x, y, w, h = (box[k] for k in "xywh")
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > 1 + 1e-9 or y + h > 1 + 1e-9:
        problems.append(f"{where}: box must lie inside the canvas (0..1), got x={x} y={y} w={w} h={h}")


def _check_color(where: str, value: Any, problems: list[str]) -> None:
    if value is not None and not (isinstance(value, str) and COLOR.match(value)):
        problems.append(f"{where}: color must be #RRGGBB or #RRGGBBAA, got {value!r}")


def _check_variables(where: str, text: str, problems: list[str]) -> None:
    for name in variables_in(text):
        if not VARIABLE_PATH.match(name):
            problems.append(f"{where}: invalid variable {{{{{name}}}}} (use letters, digits, _ and dots)")


def validate(template: Any) -> list[str]:
    """Return a list of problems; empty means the template can be rendered."""
    problems: list[str] = []
    if not isinstance(template, dict):
        return ["template must be a JSON object"]
    if template.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version must be {SCHEMA_VERSION}")

    canvas = template.get("canvas")
    if canvas is not None:
        w, h = (canvas or {}).get("width"), (canvas or {}).get("height")
        if not (isinstance(w, int) and isinstance(h, int) and 0 < w <= MAX_SIDE and 0 < h <= MAX_SIDE
                and w * h <= MAX_PIXELS):
            problems.append(f"canvas must be whole pixels, at most {MAX_SIDE} per side and {MAX_PIXELS} in total")

    background = template.get("background")
    if not isinstance(background, dict) or not ({"color", "asset"} & background.keys()):
        problems.append("background needs a color or an asset")
    else:
        _check_color("background", background.get("color"), problems)
        if "asset" in background and not ASSET_ID.match(str(background["asset"])):
            problems.append(f"background: asset id must match {ASSET_ID.pattern}")
        if canvas is None and "asset" not in background:
            problems.append("canvas is required when the background is a color")

    layers = template.get("layers", [])
    if not isinstance(layers, list) or len(layers) > MAX_LAYERS:
        problems.append(f"layers must be a list of at most {MAX_LAYERS}")
        return problems
    for i, layer in enumerate(layers):
        where = f"layer {i}"
        if not isinstance(layer, dict):
            problems.append(f"{where}: must be an object")
            continue
        kind = layer.get("type")
        if kind not in ("text", "qr", "image"):
            problems.append(f"{where}: unknown layer type {kind!r}")
            continue
        _check_box(where, layer.get("box"), problems)
        if kind == "text":
            text = layer.get("text")
            if not isinstance(text, str) or len(text) > MAX_TEXT:
                problems.append(f"{where}: text must be a string of at most {MAX_TEXT} characters")
            else:
                _check_variables(where, text, problems)
            size = layer.get("size")
            if not (_number(size) and 0 < size <= MAX_TEXT_SIZE):
                problems.append(f"{where}: size must be a fraction of canvas height in (0, {MAX_TEXT_SIZE}]")
            _check_color(where, layer.get("color"), problems)
            if layer.get("align", "center") not in ALIGNS:
                problems.append(f"{where}: align must be one of {sorted(ALIGNS)}")
            if layer.get("font", "noto-sans") not in FONTS:
                problems.append(f"{where}: font must be one of {sorted(FONTS)}")
        elif kind == "qr":
            data = layer.get("data")
            if not isinstance(data, str) or not data or len(data) > MAX_QR:
                problems.append(f"{where}: qr data must be a non-empty string of at most {MAX_QR} characters")
            else:
                _check_variables(where, data, problems)
            _check_color(where, layer.get("color"), problems)
            _check_color(where, layer.get("background"), problems)
        elif kind == "image":
            if not ASSET_ID.match(str(layer.get("asset", ""))):
                problems.append(f"{where}: asset id must match {ASSET_ID.pattern}")
    return problems
