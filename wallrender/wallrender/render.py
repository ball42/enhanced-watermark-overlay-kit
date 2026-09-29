"""Draw a validated template. Pure: no network, no Flask, no Jamf.

The same function runs in EWOK's preview and in JAWA Brander, so what is
designed is what the device receives. Templates and values are untrusted
(this runs on the JAWA server), so every step is bounded in CPU and memory,
and any failure surfaces as TemplateError."""

from __future__ import annotations

import io
import logging
import math
import warnings
from importlib import resources
from typing import Any, Callable, Union

import qrcode
import qrcode.exceptions
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from .schema import MAX_PIXELS, MAX_QR, MAX_SIDE, TemplateError, validate
from .variables import substitute

logger = logging.getLogger("wallrender")

AssetData = Union[bytes, Image.Image]
AssetResolver = Callable[[str], AssetData]

MIN_FONT_PX = 6
MAX_ASPECT = 50  # assets thinner than 1:50 would force enormous resizes
ASSET_FORMATS = ["PNG", "JPEG"]  # never EPS/PS (Ghostscript) or other exotic decoders


def _font_bytes() -> bytes:
    return (resources.files("wallrender") / "fonts" / "NotoSans.ttf").read_bytes()


_FONT_BYTES = _font_bytes()  # read-only and shared; FreeTypeFont objects are per render


class _Session:
    """Per-render caches: fonts (FreeTypeFont is not documented as thread-safe)
    and decoded assets (so a logo used in several layers is decoded once)."""

    def __init__(self, assets: AssetResolver):
        self._resolve = assets
        self._fonts: dict[int, ImageFont.FreeTypeFont] = {}
        self._assets: dict[str, Image.Image] = {}

    def font(self, px: int) -> ImageFont.FreeTypeFont:
        if px not in self._fonts:
            # BASIC layout keeps output identical across hosts (no Raqm);
            # the variable font is pinned to its Regular instance.
            f = ImageFont.truetype(io.BytesIO(_FONT_BYTES), px, layout_engine=ImageFont.Layout.BASIC)
            try:
                f.set_variation_by_name("Regular")
            except (OSError, ValueError):
                pass
            self._fonts[px] = f
        return self._fonts[px]

    def asset(self, asset_id: str) -> Image.Image:
        if asset_id not in self._assets:
            try:
                data = self._resolve(asset_id)
            except KeyError as e:
                raise TemplateError([f"asset {asset_id!r} not found"]) from e
            self._assets[asset_id] = _open(asset_id, data)
        return self._assets[asset_id]


def _check_size(asset_id: str, width: int, height: int) -> None:
    if width > MAX_SIDE or height > MAX_SIDE or width * height > MAX_PIXELS:
        raise TemplateError([f"asset {asset_id!r} is too large ({width}x{height}; "
                             f"at most {MAX_SIDE} per side and {MAX_PIXELS} pixels)"])
    if max(width, height) > MAX_ASPECT * min(width, height):
        raise TemplateError([f"asset {asset_id!r} has an extreme aspect ratio ({width}x{height})"])


def _open(asset_id: str, data: AssetData) -> Image.Image:
    # _check_size is the real bound; Pillow's global bomb check is only a
    # backstop, and its warning or error must not escape as a raw exception.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        if isinstance(data, Image.Image):
            img = data
        else:
            try:
                img = Image.open(io.BytesIO(data), formats=ASSET_FORMATS)
            except Image.DecompressionBombError as e:
                raise TemplateError([f"asset {asset_id!r} is too large"]) from e
            except (UnidentifiedImageError, OSError, TypeError) as e:
                raise TemplateError([f"asset {asset_id!r} must be a PNG or JPEG image"]) from e
        _check_size(asset_id, *img.size)  # before load(): nothing is decoded yet
        try:
            img.load()
        except Image.DecompressionBombError as e:
            raise TemplateError([f"asset {asset_id!r} is too large"]) from e
    img = ImageOps.exif_transpose(img)
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
    return (round(box["x"] * w), round(box["y"] * h), max(1, round(box["w"] * w)), max(1, round(box["h"] * h)))


def _canvas(template: dict[str, Any], session: _Session) -> Image.Image:
    background = template["background"]
    canvas = template.get("canvas")
    if "asset" in background:
        bg = session.asset(background["asset"])
        if canvas:
            # fit() crops in source space before resizing, so no intermediate
            # is ever larger than the canvas.
            bg = ImageOps.fit(bg, (canvas["width"], canvas["height"]), Image.Resampling.LANCZOS)
        return bg.copy()
    return Image.new("RGBA", (canvas["width"], canvas["height"]), _rgba(background["color"], (0, 0, 0, 255)))


def _fit_font(session: _Session, text: str, px: int, bw: int, bh: int):
    """Largest size <= px whose text fits the box: one measurement plus a few
    checks, never a pixel-by-pixel walk down from a huge size."""
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    for _ in range(4):
        f = session.font(px)
        left, top, right, bottom = probe.textbbox((0, 0), text, font=f)
        width, height = right - left, bottom - top
        if (width <= bw and height <= bh) or px <= MIN_FONT_PX:
            return f, (left, top, width, height)
        scale = min(bw / max(width, 1), bh / max(height, 1))
        px = max(MIN_FONT_PX, min(px - 1, math.floor(px * scale)))
    f = session.font(px)
    left, top, right, bottom = probe.textbbox((0, 0), text, font=f)
    return f, (left, top, right - left, bottom - top)


def _draw_text(img: Image.Image, session: _Session, layer: dict[str, Any],
               values: dict[str, Any], missing: list[str]) -> None:
    text = substitute(layer["text"], values, missing)
    if not text.strip():
        return
    bx, by, bw, bh = _box_px(layer["box"], img.size)
    px = max(MIN_FONT_PX, round(layer["size"] * img.height))
    f, (left, top, width, height) = _fit_font(session, text, px, bw, bh)
    align = layer.get("align", "center")
    x = 0 if align == "left" else bw - width if align == "right" else (bw - width) // 2
    y = (bh - height) // 2
    # Draw into a box-sized layer: bounded memory, and nothing spills outside the box.
    box_layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    ImageDraw.Draw(box_layer).text((x - left, y - top), text, font=f,
                                   fill=_rgba(layer.get("color"), (255, 255, 255, 255)))
    img.alpha_composite(box_layer, (bx, by))


def _draw_qr(img: Image.Image, layer: dict[str, Any], values: dict[str, Any], missing: list[str]) -> None:
    data = substitute(layer["data"], values, missing, limit=None)
    if not data:
        return
    if len(data) > MAX_QR:
        # Never truncate: a shortened QR code would silently point somewhere else.
        raise TemplateError([f"qr data is {len(data)} characters after substitution; the limit is {MAX_QR}"])
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1, border=2)
    qr.add_data(data.encode("utf-8", "replace"))
    try:
        qr.make(fit=True)
    except (qrcode.exceptions.DataOverflowError, ValueError) as e:
        raise TemplateError([f"qr data is too long to encode ({len(data)} characters)"]) from e
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


def _draw_image(img: Image.Image, session: _Session, layer: dict[str, Any]) -> None:
    src = session.asset(layer["asset"])
    bx, by, bw, bh = _box_px(layer["box"], img.size)
    scale = min(bw / src.width, bh / src.height)
    size = (max(1, round(src.width * scale)), max(1, round(src.height * scale)))
    fitted = src.resize(size, Image.Resampling.LANCZOS)
    img.alpha_composite(fitted, (bx + (bw - fitted.width) // 2, by + (bh - fitted.height) // 2))


def _flatten(img: Image.Image) -> Image.Image:
    """Transparent areas render black: a defined result for the delivered PNG."""
    base = Image.new("RGBA", img.size, (0, 0, 0, 255))
    base.alpha_composite(img)
    return base.convert("RGB")


def render_with_report(template: dict[str, Any], values: dict[str, Any],
                       assets: AssetResolver) -> tuple[Image.Image, list[str]]:
    """Render and also return the variable paths that had no printable value.

    Raises only TemplateError, whatever the template, values or assets contain."""
    problems = validate(template)
    if problems:
        raise TemplateError(problems)
    session = _Session(assets)
    missing: list[str] = []
    try:
        img = _canvas(template, session)
        for layer in template.get("layers", []):
            kind = layer["type"]
            if kind == "text":
                _draw_text(img, session, layer, values, missing)
            elif kind == "qr":
                _draw_qr(img, layer, values, missing)
            else:
                _draw_image(img, session, layer)
        return _flatten(img), missing
    except TemplateError:
        raise
    except (ValueError, TypeError, OverflowError, UnicodeError, OSError, MemoryError) as e:
        # Logged with its traceback so a genuine bug is not disguised as bad input.
        logger.exception("wallrender: render failed")
        raise TemplateError([f"render failed: {type(e).__name__}: {e}"]) from e


def render(template: dict[str, Any], values: dict[str, Any], assets: AssetResolver) -> Image.Image:
    """Render a template with device values into an RGB image ready to deliver."""
    return render_with_report(template, values, assets)[0]


def _missing_glyphs(session: _Session, text: str, notdef: bytes) -> list[str]:
    def pixels(ch: str) -> bytes:
        img = Image.new("L", (96, 96), 0)
        ImageDraw.Draw(img).text((16, 16), ch, font=session.font(48), fill=255)
        return img.tobytes()

    return sorted({ch for ch in set(text) if not ch.isspace() and pixels(ch) == notdef})


def lint(template: dict[str, Any], values: dict[str, Any], assets: AssetResolver) -> list[str]:
    """Warnings a designer should see: invalid template, missing values, missing glyphs."""
    problems = validate(template)
    if problems:
        return problems
    warnings: list[str] = []
    try:
        _, missing = render_with_report(template, values, assets)
    except TemplateError as e:
        return e.problems
    for path in sorted(set(missing)):
        warnings.append(f"no value for {{{{{path}}}}}; it renders empty")
    session = _Session(assets)
    notdef_img = Image.new("L", (96, 96), 0)
    ImageDraw.Draw(notdef_img).text((16, 16), "\U0010FFFD", font=session.font(48), fill=255)
    notdef = notdef_img.tobytes()  # the fallback box: a code point no font covers
    for i, layer in enumerate(template.get("layers", [])):
        if layer["type"] == "text":
            for ch in _missing_glyphs(session, substitute(layer["text"], values), notdef):
                warnings.append(f"layer {i}: the font has no glyph for {ch!r} ({ch}); it will show as a box")
    return warnings
