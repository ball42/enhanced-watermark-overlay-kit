"""Draw a validated template. Pure: no network, no Flask, no Jamf.

The same function runs in EWOK's preview and in JAWA Brander, so what is
designed is what the device receives."""

from __future__ import annotations

import io
from functools import lru_cache
from importlib import resources
from typing import Any, Callable, Union

import qrcode
from PIL import Image, ImageDraw, ImageFont

from .schema import TemplateError, validate
from .variables import substitute

AssetData = Union[bytes, Image.Image]
AssetResolver = Callable[[str], AssetData]

MIN_FONT_PX = 6


def _font_path() -> str:
    return str(resources.files("wallrender") / "fonts" / "NotoSans.ttf")


@lru_cache(maxsize=64)
def font(px: int) -> ImageFont.FreeTypeFont:
    # BASIC layout keeps output identical across hosts (no Raqm dependency);
    # the variable font is pinned to its Regular instance.
    f = ImageFont.truetype(_font_path(), px, layout_engine=ImageFont.Layout.BASIC)
    try:
        f.set_variation_by_name("Regular")
    except (OSError, ValueError):
        pass
    return f


def _open(data: AssetData) -> Image.Image:
    img = data if isinstance(data, Image.Image) else Image.open(io.BytesIO(data))
    img.load()
    return img.convert("RGBA")


def _rgba(hex_color: str | None, default: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if not hex_color:
        return default
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    a = int(h[6:8], 16) if len(h) == 8 else 255
    return (r, g, b, a)


def _box_px(box: dict[str, float], size: tuple[int, int]) -> tuple[int, int, int, int]:
    w, h = size
    return (round(box["x"] * w), round(box["y"] * h), round(box["w"] * w), round(box["h"] * h))


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Scale to cover the canvas and centre-crop, keeping the aspect ratio."""
    scale = max(size[0] / img.width, size[1] / img.height)
    resized = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))),
                         Image.Resampling.LANCZOS)
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


def _canvas(template: dict[str, Any], assets: AssetResolver) -> Image.Image:
    background = template["background"]
    canvas = template.get("canvas")
    if "asset" in background:
        bg = _open(assets(background["asset"]))
        if canvas:
            bg = _cover(bg, (canvas["width"], canvas["height"]))
        return bg
    return Image.new("RGBA", (canvas["width"], canvas["height"]), _rgba(background["color"], (0, 0, 0, 255)))


def _draw_text(img: Image.Image, layer: dict[str, Any], values: dict[str, Any], missing: list[str]) -> None:
    text = substitute(layer["text"], values, missing)
    if not text.strip():
        return
    bx, by, bw, bh = _box_px(layer["box"], img.size)
    px = max(MIN_FONT_PX, round(layer["size"] * img.height))
    draw = ImageDraw.Draw(img)
    # Overflow policy v0: shrink until the text fits the box width.
    while True:
        f = font(px)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=f)
        if right - left <= bw or px <= MIN_FONT_PX:
            break
        px -= 1
    width, height = right - left, bottom - top
    align = layer.get("align", "center")
    x = bx if align == "left" else bx + bw - width if align == "right" else bx + (bw - width) / 2
    y = by + (bh - height) / 2
    layer_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer_img).text((x - left, y - top), text, font=f,
                                   fill=_rgba(layer.get("color"), (255, 255, 255, 255)))
    img.alpha_composite(layer_img)


def _draw_qr(img: Image.Image, layer: dict[str, Any], values: dict[str, Any], missing: list[str]) -> None:
    data = substitute(layer["data"], values, missing)
    if not data:
        return
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    dark = _rgba(layer.get("color"), (0, 0, 0, 255))
    light = _rgba(layer.get("background"), (255, 255, 255, 255))
    matrix = qr.get_matrix()  # includes the quiet-zone border, which scanners need
    modules = len(matrix)
    bx, by, bw, bh = _box_px(layer["box"], img.size)
    side = min(bw, bh) // modules * modules  # whole pixels per module keeps edges crisp
    if side <= 0:
        return
    code = Image.new("RGBA", (modules, modules), light)
    code.putdata([dark if cell else light for row in matrix for cell in row])
    code = code.resize((side, side), Image.Resampling.NEAREST)
    img.alpha_composite(code, (bx + (bw - side) // 2, by + (bh - side) // 2))


def _draw_image(img: Image.Image, layer: dict[str, Any], assets: AssetResolver) -> None:
    src = _open(assets(layer["asset"]))
    bx, by, bw, bh = _box_px(layer["box"], img.size)
    scale = min(bw / src.width, bh / src.height)
    fitted = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))),
                        Image.Resampling.LANCZOS)
    img.alpha_composite(fitted, (bx + (bw - fitted.width) // 2, by + (bh - fitted.height) // 2))


def render_with_report(template: dict[str, Any], values: dict[str, Any],
                       assets: AssetResolver) -> tuple[Image.Image, list[str]]:
    """Render and also return the variable paths that had no value."""
    problems = validate(template)
    if problems:
        raise TemplateError(problems)
    img = _canvas(template, assets)
    missing: list[str] = []
    for layer in template.get("layers", []):
        kind = layer["type"]
        if kind == "text":
            _draw_text(img, layer, values, missing)
        elif kind == "qr":
            _draw_qr(img, layer, values, missing)
        else:
            _draw_image(img, layer, assets)
    return img.convert("RGB"), missing


def render(template: dict[str, Any], values: dict[str, Any], assets: AssetResolver) -> Image.Image:
    """Render a template with device values into an RGB image ready to deliver."""
    return render_with_report(template, values, assets)[0]


def _glyph_pixels(ch: str) -> bytes:
    img = Image.new("L", (96, 96), 0)
    ImageDraw.Draw(img).text((16, 16), ch, font=font(48), fill=255)
    return img.tobytes()


def _missing_glyphs(text: str) -> list[str]:
    notdef = _glyph_pixels("\U0010FFFD")  # a code point no font covers: the fallback box
    return sorted({ch for ch in text if not ch.isspace() and _glyph_pixels(ch) == notdef})


def lint(template: dict[str, Any], values: dict[str, Any], assets: AssetResolver) -> list[str]:
    """Warnings a designer should see: invalid template, missing values, missing glyphs."""
    problems = validate(template)
    if problems:
        return problems
    warnings: list[str] = []
    _, missing = render_with_report(template, values, assets)
    for path in sorted(set(missing)):
        warnings.append(f"no value for {{{{{path}}}}}; it renders empty")
    for i, layer in enumerate(template.get("layers", [])):
        if layer["type"] == "text":
            for ch in _missing_glyphs(substitute(layer["text"], values)):
                warnings.append(f"layer {i}: the font has no glyph for {ch!r} ({ch}); it will show as a box")
    return warnings
