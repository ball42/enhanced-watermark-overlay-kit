"""Template mode API: render previews through wallrender, and keep the
library of template assets (backgrounds and logos) by asset id.

Everything here is local-only like the rest of EWOK, but templates and
uploads are still treated as untrusted: wallrender bounds the render,
asset ids follow wallrender's pattern, and only PNG and JPEG are kept.
"""

import base64
import hashlib
import io
import json
import math
import os
import re
import shutil
import time
import zipfile

from flask import Blueprint, jsonify, request, send_file
from PIL import Image, ImageOps, UnidentifiedImageError

import config
import wallrender
from wallrender import AssetCache, TemplateError, render_with_lint, required_version, validate
from wallrender.cli import folder_assets, role_keys, stress_values
from wallrender.devices import fit_warnings
from wallrender.render import (LARGE_TEXT, MIN_FONT_PX, READABLE_MIN, _box_px, _fit_font, _lint_warnings,
                               _over, _render, _rgba, _Session, worst_contrast)
from wallrender.roles import resolve
from wallrender.variables import substitute
from wallrender.schema import ASSET_ID, MAX_PIXELS, MAX_SIDE, newer_than
from utils.pillow_target import pillow_check

template_bp = Blueprint("template_api", __name__, url_prefix="/api/template")

FORMATS = {"PNG": "png", "JPEG": "jpg"}
EXTENSIONS = ("png", "jpg", "jpeg")
GONE = "That asset is no longer in the library."
MAX_BUNDLE_ENTRIES = 60
MAX_BUNDLE_BYTES = 64 * 1024 * 1024  # uncompressed, checked before reading
# A deleted asset waits in <assets>/.trash for a day, so Delete can be undone
# (and a template that still names it can get it back). An asset replaced by
# an upload or an opened template waits in .trash/replaced the same way.
# Each copy keeps its own stamped name, so a second replace or delete of the
# same id within the day keeps the first; restore takes the newest.
TRASH = ".trash"
REPLACED = "replaced"
TRASH_DAYS = 1
TRASHED_NAME = re.compile(
    rf"(?P<id>{ASSET_ID.pattern})(?:\.(?P<stamp>[0-9]{{1,20}}))?\.(?:{'|'.join(EXTENSIONS)})")
# Decoded assets and resized image layers, shared by every render: a preview
# after each edit and each device of a check reuse them instead of decoding a
# 2000 px logo again. Keyed by a digest of the file's bytes, so a replaced
# asset is never drawn stale.
ASSET_CACHE = AssetCache()


def _folder():
    os.makedirs(config.TEMPLATE_ASSETS_FOLDER, exist_ok=True)
    return config.TEMPLATE_ASSETS_FOLDER


def _png_data_url(image):
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


# A photo background makes the full-size render an 8-12 MB PNG that takes
# 0.25 s to encode, for an image the page shows a few hundred pixels wide. So
# the on-screen preview of a render over an asset background is a JPEG (about
# 1.2 MB and 16 ms for a grainy 1290x2796 photo); Download preview fetches the
# lossless PNG from /preview.png instead.
PREVIEW_JPEG_QUALITY = 82


def _preview_data_url(image, template, values):
    resolved, _ = resolve(template, values)
    if "asset" not in (resolved.get("background") or {}):
        return _png_data_url(image)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=PREVIEW_JPEG_QUALITY)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


MAX_DEVICES = 20


def _json_body():
    """The request's JSON, or None (including JSON nested too deeply)."""
    try:
        return request.get_json(silent=True)
    except RecursionError:
        return None


def _describe(template, values, size, hidden):
    """What the render shows, for the preview image's alt: the canvas, then each
    text and QR layer drawn, with its substituted value, in layer order."""
    template, values = resolve(template, values)  # role.* text comes from the variant
    gone = {index for index, _ in hidden}
    parts = []
    for index, layer in enumerate(template.get("layers", [])):
        if index in gone or layer["type"] not in ("text", "qr"):
            continue
        if layer["type"] == "text":
            text = " ".join(substitute(layer["text"], values).split())
            if text:
                parts.append(f"text '{text}'")
        else:
            data = substitute(layer["data"], values, limit=None)
            if data:
                parts.append(f"QR {data}")
    head = f"{size[0]}×{size[1]} wallpaper"
    return f"{head}: {', '.join(parts)}" if parts else f"{head} with no text or QR"


def _render_one(template, values, assets, label, devices=(), screen="lock"):
    # render_with_lint(), keeping the text fits so low contrast can carry its fix.
    image, missing, fits, hidden, qrs = _render(template, values, assets, fits=[], hidden=[], qrs=[],
                                                cache=ASSET_CACHE)
    warnings = _lint_warnings(template, values, assets, image, missing, fits, hidden, qrs)
    return {"label": label, "image": _preview_data_url(image, template, values),
            "description": _describe(template, values, image.size, hidden),
            "warnings": warnings, "kinds": [warning_kind(w) for w in warnings],
            "contrast": _contrast_fixes(fits, image.height),
            "device_warnings": fit_warnings(template, image.size, list(devices), screen)}


# The fixes a low-contrast warning offers. Each is held to the worst part of
# what is behind the text (wallrender's behind_cells), as lint is. Text
# colours are opaque, so the ratio after the change is exact: what is behind
# the text does not move.
FIX_TEXT = (("white", "#FFFFFF"), ("dark", "#111111"))
BACKDROP_COLORS = ("#000000", "#FFFFFF")
BACKDROP_STEP = 0.05  # the opacity field's step
BACKDROP_MARGIN = 0.015  # of the canvas around the text, as Add panel behind uses (template.js PANEL_MARGIN)
BACKDROP_RADIUS = 0.12
BACKDROP_TRIES = 6  # real renders to confirm one; the sampled cells are almost always exact


def _needed(fit, height):
    return 3.0 if fit.used >= LARGE_TEXT * height else 4.5


def _text_ratio(fit, cells=None):
    return worst_contrast(fit.color, fit.cells if cells is None else cells)


def _contrast_fixes(fits, height):
    """For each text layer below WCAG's ratio: its ratio, the ratio it needs,
    and the plain text colour that passes (the better of white and dark), if one does."""
    fixes = []
    for fit in fits:
        ratio, needed = _text_ratio(fit), _needed(fit, height)
        if ratio >= needed:
            continue
        name, color, best = max(((n, c, worst_contrast(_rgba(c, (0, 0, 0, 255)), fit.cells))
                                 for n, c in FIX_TEXT), key=lambda option: option[2])
        fixes.append({"index": fit.index, "ratio": round(ratio, 2), "needed": needed,
                      "text": {"name": name, "color": color, "ratio": round(best, 2)} if best >= needed else None})
    return fixes


@template_bp.route("/preview", methods=["POST"])
def preview():
    body = _json_body()
    if not isinstance(body, dict) or not isinstance(body.get("values"), dict) \
            or "template" not in body:
        return jsonify({"error": "Send JSON with a template and a values object."}), 400
    template, values = body["template"], body["values"]
    devices = body.get("devices") or []
    screen = body.get("screen", "lock")
    if screen not in ("lock", "home") or not isinstance(devices, list) \
            or not all(isinstance(d, str) for d in devices) or len(devices) > MAX_DEVICES:
        return jsonify({"error": f"devices must be a list of at most {MAX_DEVICES} ids, "
                                 "and screen lock or home."}), 400
    problems = validate(template)
    if problems:
        return jsonify({"problems": problems}), 400
    assets = folder_assets(_folder())
    variants = [("sample", values)]
    if body.get("stress"):
        variants += [("long", stress_values(template)), ("empty", {})]
        # Each role variant with the sample device, as `wallrender preview --stress` does.
        variants += [(f"role {key}", dict(values, role=key)) for key in role_keys(template)]
    try:
        renders = [_render_one(template, v, assets, label, devices if label == "sample" else (), screen)
                   for label, v in variants]
    except TemplateError as err:
        return jsonify({"problems": err.problems}), 422
    # The values each stress render used, so a low-contrast fix under it
    # (Add a backdrop) works out the panel for that render, not the sample.
    for render, (_, v) in zip(renders[1:], variants[1:]):
        render["values"] = v
    newer = newer_than(template, config.WALLRENDER_TARGET)
    renders[0]["warnings"] = newer + renders[0]["warnings"]
    renders[0]["kinds"] = ["target"] * len(newer) + renders[0]["kinds"]
    # For the JAWA preflight: whether the release JAWA runs renders this template.
    target = ".".join(config.WALLRENDER_TARGET.split(".")[:2])
    # And whether EWOK measures text with the Pillow JAWA renders with.
    return jsonify({"renders": renders, "target": {"version": target, "renders": not newer,
                                                   "pillow": pillow_check()}})


@template_bp.route("/preview.png", methods=["POST"])
def preview_png():
    """The sample render as a lossless PNG, the same pixels as
    `wallrender preview`: what Download preview saves."""
    body = _json_body()
    if not isinstance(body, dict) or not isinstance(body.get("values"), dict) \
            or "template" not in body:
        return jsonify({"error": "Send JSON with a template and a values object."}), 400
    problems = validate(body["template"])
    if problems:
        return jsonify({"problems": problems}), 400
    try:
        image, _ = render_with_lint(body["template"], body["values"], folder_assets(_folder()),
                                    cache=ASSET_CACHE)
    except TemplateError as err:
        return jsonify({"problems": err.problems}), 422
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


def _backdrop_box(box):
    x, y = max(0.0, box["x"] - BACKDROP_MARGIN), max(0.0, box["y"] - BACKDROP_MARGIN)
    return {"x": round(x, 4), "y": round(y, 4),
            "w": round(min(1.0, box["x"] + box["w"] + BACKDROP_MARGIN) - x, 4),
            "h": round(min(1.0, box["y"] + box["h"] + BACKDROP_MARGIN) - y, 4)}


def _backdrop_options(fit, needed):
    """(opacity, colour) pairs that reach the ratio over every sampled cell
    behind the text, lowest opacity first: what to try for real, in order."""
    options = []
    for color in BACKDROP_COLORS:
        rgb = _rgba(color, (0, 0, 0, 255))[:3]
        for step in range(1, round(1 / BACKDROP_STEP) + 1):
            opacity = round(step * BACKDROP_STEP, 2)
            seen = [_over((*rgb, round(255 * opacity)), cell) for cell in fit.cells]
            if _text_ratio(fit, seen) >= needed:
                options += [(o / 100, color) for o in range(round(opacity * 100), 101, round(BACKDROP_STEP * 100))]
                break
    return sorted(options)


@template_bp.route("/backdrop", methods=["POST"])
def backdrop():
    """For a low-contrast warning's "Add a backdrop": the panel to put just
    behind a text layer, at the lowest opacity a real render confirms reaches
    WCAG's ratio. Changes nothing; the page inserts the panel."""
    body = _json_body()
    if not isinstance(body, dict) or not isinstance(body.get("values"), dict) \
            or "template" not in body or type(body.get("index")) is not int:
        return jsonify({"error": "Send JSON with a template, a values object and a layer index."}), 400
    template, values, index = body["template"], body["values"], body["index"]
    problems = validate(template)
    if problems:
        return jsonify({"problems": problems}), 400
    if not 0 <= index < len(template["layers"]) or template["layers"][index]["type"] != "text":
        return jsonify({"error": "The index must be the number of a text layer."}), 400
    assets = folder_assets(_folder())
    try:
        image, _, fits, _, _ = _render(template, values, assets, fits=[], cache=ASSET_CACHE)
        fit = next((f for f in fits if f.index == index), None)
        if fit is None:
            return jsonify({"error": f"Layer {index + 1} prints no text for this device."}), 422
        needed, before = _needed(fit, image.height), _text_ratio(fit)
        result = {"index": index, "from": round(before, 2), "needed": needed}
        if before >= needed:
            return jsonify({**result, "panel": None, "to": round(before, 2)})
        box = _backdrop_box(template["layers"][index]["box"])
        for opacity, color in _backdrop_options(fit, needed)[:BACKDROP_TRIES]:
            panel = {"type": "panel", "box": box, "color": color, "opacity": opacity, "radius": BACKDROP_RADIUS}
            trial = json.loads(json.dumps(template))
            trial["layers"].insert(index, panel)
            if validate(trial):
                return jsonify({"error": "The template has no room for another layer."}), 422
            _, _, trial_fits, _, _ = _render(trial, values, assets, fits=[], cache=ASSET_CACHE)
            after = next(f for f in trial_fits if f.index == index + 1)
            ratio = _text_ratio(after)
            if ratio >= needed:
                return jsonify({**result, "panel": panel, "to": round(ratio, 2)})
    except TemplateError as err:
        return jsonify({"problems": err.problems}), 422
    return jsonify({**result, "panel": None, "to": round(before, 2),
                    "error": "No backdrop reaches the ratio with this text color; change the text color instead."})


MAX_BATCH = 200
THUMB_WIDTH = 240


def _thumb(image):
    """The device check's thumbnail, at most THUMB_WIDTH wide. Image.reduce()
    averages whole blocks of pixels: about 3 ms on a 1290x2796 render, where
    thumbnail()'s resample took about 12. The sheet shows it at most 160 px
    tall, so the plain box average looks the same there."""
    return image.reduce(max(1, math.ceil(image.width / THUMB_WIDTH)))


@template_bp.route("/preview-batch", methods=["POST"])
def preview_batch():
    """Render one template for many devices (a CSV the designer loaded in the
    browser) and return a small thumbnail and the warnings for each. The
    values are used for this request only and never stored. The page sends
    the list in chunks; `first` is the number of the chunk's first device, so
    an unnamed one is still called by its row in the file."""
    body = _json_body()
    devices = body.get("devices") if isinstance(body, dict) else None
    if not isinstance(devices, list) or "template" not in body \
            or not all(isinstance(d, dict) for d in devices):
        return jsonify({"error": "Send JSON with a template and a devices list of value objects."}), 400
    if len(devices) > MAX_BATCH:
        return jsonify({"error": f"At most {MAX_BATCH} devices at a time."}), 400
    first = body.get("first", 1)
    if type(first) is not int or first < 1:
        return jsonify({"error": "first must be a whole number from 1."}), 400
    template = body["template"]
    problems = validate(template)
    if problems:
        return jsonify({"problems": problems}), 400
    assets = folder_assets(_folder())
    results = []
    cpu_started = time.thread_time()
    try:
        for n, values in enumerate(devices, first):
            # The same render and lint as render_with_lint(), keeping the text
            # sizes it measured so the summary can name the smallest one.
            image, missing, fits, hidden, qrs = _render(template, values, assets, fits=[], hidden=[],
                                                        qrs=[], cache=ASSET_CACHE)
            warnings = _lint_warnings(template, values, assets, image, missing, fits, hidden, qrs)
            smallest = min(fits, key=lambda f: f.used, default=None)
            image = _thumb(image)
            label = values.get("device_name") or values.get("serial_number") or f"Device {n}"
            results.append({
                "label": str(label), "warnings": warnings, "kinds": [warning_kind(w) for w in warnings],
                "smallest_text": smallest and {"px": smallest.used, "layer": smallest.index},
                "thumb": _png_data_url(image),
            })
    except TemplateError as err:
        return jsonify({"problems": err.problems}), 422
    response = jsonify({"results": results, "readable_px": math.ceil(READABLE_MIN * template["canvas"]["height"])})
    # CPU time of this request's thread, which a busy machine does not inflate
    # the way it does wall time; the device check's budget test reads it.
    cpu_ms = (time.thread_time() - cpu_started) * 1000
    response.headers["Server-Timing"] = f'render;dur={cpu_ms:.1f};desc="CPU"'
    return response


NAME_KINDS = ("shrank", "cut_off", "too_small")
SIZE_STEP = 1000  # the size field's step is 0.001 of canvas height
FIT_CHECKS = 5  # the devices a fitted size is rendered for, tightest first


def _layer_warns(template, values, assets, index):
    """Whether lint says this text layer shrank, was shortened or is cut off."""
    image, missing, fits, hidden, qrs = _render(template, values, assets, fits=[], hidden=[], qrs=[],
                                                cache=ASSET_CACHE)
    warnings = _lint_warnings(template, values, assets, image, missing, fits, hidden, qrs)
    return any(re.match(rf"layer {index}:", w) and warning_kind(w) in NAME_KINDS for w in warnings)


def _fit_layer(template, index, devices, assets):
    """The largest size (a step of the size field) at which this text layer
    prints every device's text without shrinking: wallrender's own fit
    measures each text, then a real render and lint confirm the tightest."""
    layer = template["layers"][index]
    width, height = template["canvas"]["width"], template["canvas"]["height"]
    _, _, bw, bh = _box_px(layer["box"], (width, height))
    px = max(MIN_FONT_PX, round(layer["size"] * height))
    session = _Session(assets)
    fitted = []
    for values in devices:
        _, resolved = resolve(template, values)
        text = substitute(layer["text"], resolved)
        if text.strip():
            font, _ = _fit_font(session, text, px, bw, bh, MIN_FONT_PX, layer.get("align", "center"),
                                layer.get("weight", "regular"))
            fitted.append((round(font.size), values))
    result = {"index": index, "from": layer["size"], "readable_px": math.ceil(READABLE_MIN * height)}
    if not fitted or min(p for p, _ in fitted) >= px:
        return {**result, "size": layer["size"], "changed": False, "fits": True}
    fitted.sort(key=lambda f: f[0])
    tightest = [v for _, v in fitted[:FIT_CHECKS]]
    size = math.floor(fitted[0][0] / height * SIZE_STEP) / SIZE_STEP
    for _ in range(4):  # hinting can leave a pixel over; step down and look again
        if round(size * height) < result["readable_px"]:
            return {**result, "size": size, "changed": False, "fits": False}
        trial = json.loads(json.dumps(template))
        trial["layers"][index]["size"] = size
        if "min_size" in layer:
            trial["layers"][index]["min_size"] = min(layer["min_size"], size)
        if not any(_layer_warns(trial, v, assets, index) for v in tightest):
            out = {**result, "size": size, "changed": True, "fits": True}
            if "min_size" in layer and layer["min_size"] > size:
                out["min_size"] = size
            return out
        size = round(size - 1 / SIZE_STEP, 3)
    return {**result, "size": size, "changed": False, "fits": False}


@template_bp.route("/fit-names", methods=["POST"])
def fit_names():
    """For the device check's "Fit the longest name": the size each named
    text layer needs so the devices sent (the ones whose names shrank) print
    without shrinking. Changes nothing; the page applies the sizes."""
    body = _json_body()
    devices = body.get("devices") if isinstance(body, dict) else None
    layers = body.get("layers") if isinstance(body, dict) else None
    if not isinstance(devices, list) or not devices or "template" not in body \
            or not all(isinstance(d, dict) for d in devices) \
            or not isinstance(layers, list) or not all(type(i) is int for i in layers):
        return jsonify({"error": "Send JSON with a template, a layers list and a devices list."}), 400
    if len(devices) > MAX_BATCH:
        return jsonify({"error": f"At most {MAX_BATCH} devices at a time."}), 400
    template = body["template"]
    problems = validate(template)
    if problems:
        return jsonify({"problems": problems}), 400
    count = len(template["layers"])
    if not all(0 <= i < count and template["layers"][i]["type"] == "text" for i in layers):
        return jsonify({"error": "Each layer must be the number of a text layer."}), 400
    assets = folder_assets(_folder())
    try:
        fitted = [_fit_layer(template, i, devices, assets) for i in dict.fromkeys(layers)]
    except TemplateError as err:
        return jsonify({"problems": err.problems}), 422
    return jsonify({"layers": fitted})


# What kind of problem a lint warning names, for the fleet summary. The
# order matters: a QR contrast warning is a QR problem, not a text one.
WARNING_KINDS = (
    ("qr", re.compile(r"\bQR\b")),
    ("cut_off", re.compile(r"cut off")),
    ("too_small", re.compile(r"too small to read")),
    ("shrank", re.compile(r"\bshrank\b|shortened")),
    ("missing", re.compile(r"no value|hidden because")),
    ("contrast", re.compile(r"low contrast")),
    ("glyph", re.compile(r"no glyph")),
    ("role", re.compile(r"\brole\b")),
)


def warning_kind(warning):
    for kind, pattern in WARNING_KINDS:
        if pattern.search(warning):
            return kind
    return "other"


def _asset_path(asset_id):
    """The stored file for an id, or None. Ids are checked, never joined raw."""
    if not ASSET_ID.fullmatch(asset_id or ""):
        return None
    for ext in EXTENSIONS:
        path = os.path.join(_folder(), f"{asset_id}.{ext}")
        if os.path.isfile(path):
            return path
    return None


def _id_from_filename(filename):
    stem = os.path.splitext(os.path.basename(filename or ""))[0].lower()
    return re.sub(r"[^a-z0-9_-]+", "-", stem).strip("-")[:64]


def _trash():
    path = os.path.join(_folder(), TRASH)
    os.makedirs(path, exist_ok=True)
    return path


def _replaced():
    path = os.path.join(_trash(), REPLACED)
    os.makedirs(path, exist_ok=True)
    return path


def _trashed_copies(asset_id, folder):
    """Every copy of an id in one trash slot, newest first. A copy is kept as
    <id>.<stamp>.<ext>, the stamp being when it went in; a plain <id>.<ext>
    from before stamps counts as the oldest."""
    copies = []
    for name in os.listdir(folder):
        match = TRASHED_NAME.fullmatch(name)
        if match and match["id"] == asset_id and os.path.isfile(os.path.join(folder, name)):
            copies.append((int(match["stamp"] or 0), name))
    return [os.path.join(folder, name) for _stamp, name in sorted(copies, reverse=True)]


def _trashed_path(asset_id, folder=None):
    """The newest trashed copy of an id (in the deleted or the replaced slot), or None."""
    if not ASSET_ID.fullmatch(asset_id or ""):
        return None
    copies = _trashed_copies(asset_id, folder or _trash())
    return copies[0] if copies else None


def _to_trash(path, folder):
    """Move a library file into a trash slot under a new stamp, so earlier
    copies of the same id stay there too until their day is up."""
    asset_id, ext = os.path.splitext(os.path.basename(path))
    stamp = time.time_ns()
    while True:
        kept = os.path.join(folder, f"{asset_id}.{stamp}{ext}")
        if not os.path.exists(kept):
            break
        stamp += 1
    shutil.move(path, kept)
    os.utime(kept)  # the day in the trash counts from now


def _empty_trash():
    """Remove what has been in the trash longer than TRASH_DAYS."""
    cutoff = time.time() - TRASH_DAYS * 24 * 3600
    for folder in (os.path.join(_folder(), TRASH), os.path.join(_folder(), TRASH, REPLACED)):
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            path = os.path.join(folder, name)
            try:
                if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except OSError:
                pass  # gone already, from another request


def _image_info(asset_id, path):
    with Image.open(path, formats=tuple(FORMATS)) as img:
        return {"id": asset_id, "width": img.width, "height": img.height}


@template_bp.route("/assets", methods=["GET"])
def list_assets():
    _empty_trash()
    assets = []
    for name in sorted(os.listdir(_folder())):
        asset_id, ext = os.path.splitext(name)
        if ext.lstrip(".") in EXTENSIONS and ASSET_ID.fullmatch(asset_id):
            try:
                assets.append(_image_info(asset_id, os.path.join(_folder(), name)))
            except (OSError, Image.DecompressionBombError):
                continue  # not a readable image: leave it out of the library
    return jsonify({"assets": assets})


def _library_files():
    """(id, path) of every asset in the library: not the trash or thumbnails."""
    for name in sorted(os.listdir(_folder())):
        asset_id, ext = os.path.splitext(name)
        path = os.path.join(_folder(), name)
        if ext.lstrip(".") in EXTENSIONS and ASSET_ID.fullmatch(asset_id) and os.path.isfile(path):
            yield asset_id, path


@template_bp.route("/assets.zip", methods=["GET"])
def download_library():
    """The whole library as one .zip: a copy to keep somewhere else."""
    files = list(_library_files())
    if not files:
        return jsonify({"error": "The asset library is empty."}), 404
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as library:  # PNG and JPEG are compressed already
        for _asset_id, path in files:
            library.write(path, os.path.basename(path))
    buffer.seek(0)
    return send_file(buffer, mimetype="application/zip", as_attachment=True,
                     download_name=f"ewok-asset-library-{time.strftime('%Y-%m-%d')}.zip")


@template_bp.route("/assets", methods=["POST"])
def upload_asset():
    upload = request.files.get("file")
    if not upload:
        return jsonify({"error": "No file provided."}), 400
    asset_id = request.form.get("id") or _id_from_filename(upload.filename)
    if not ASSET_ID.fullmatch(asset_id):
        return jsonify({"error": "Asset ids use lowercase letters, digits, - and _ "
                                 "(at most 64)."}), 400
    stored, error = _store_asset(asset_id, upload.read())
    if error:
        return jsonify({"error": error}), 400
    return jsonify(stored), 201


def _check_asset(data):
    """(format, width, height) if data really is a PNG or JPEG within
    wallrender's limits, else an error sentence."""
    try:
        with Image.open(io.BytesIO(data), formats=tuple(FORMATS)) as img:
            fmt, width, height = img.format, img.width, img.height
            img.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return "That file is not a readable PNG or JPEG image."
    if fmt not in FORMATS:
        return "Assets must be PNG or JPEG."
    if max(width, height) > MAX_SIDE or width * height > MAX_PIXELS:
        return f"Assets are limited to {MAX_SIDE}px per side."
    return fmt, width, height


def _same_bytes(path, data):
    with open(path, "rb") as handle:
        return handle.read() == data


def _store_asset(asset_id, data):
    """Keep data as <id>.png or .jpg. A different file already under that id
    moves to the trash's replaced slot for a day, so restore can bring it
    back. Returns (info, None) or (None, error)."""
    checked = _check_asset(data)
    if isinstance(checked, str):
        return None, checked
    fmt, width, height = checked
    info = {"id": asset_id, "width": width, "height": height}
    old = _asset_path(asset_id)
    if old and _same_bytes(old, data):
        return info, None
    _empty_trash()
    if old:
        _to_trash(old, _replaced())
    with open(os.path.join(_folder(), f"{asset_id}.{FORMATS[fmt]}"), "wb") as handle:
        handle.write(data)
    return info, None


@template_bp.route("/assets/<asset_id>", methods=["GET"])
def serve_asset(asset_id):
    path = _asset_path(asset_id)
    if not path:
        return jsonify({"error": GONE}), 404
    return send_file(path)


# The library shows each asset at 40 px, so it gets a small thumbnail rather
# than the original (a phone photo is 2 MB, a 12 MP one 7 MB, and the page
# loads them all with the Assets panel closed). Each thumbnail is made once
# and kept in <assets>/.thumbs under the original's mtime and size, so a
# replaced or restored asset gets a new one. Rendering, Download and the
# exports still read the original.
THUMBS = ".thumbs"
THUMB_SIDE = 96
THUMB_JPEG_QUALITY = 85


def _thumb_path(asset_id, path):
    """The cached thumbnail of an asset file, made on first use."""
    folder = os.path.join(_folder(), THUMBS)
    os.makedirs(folder, exist_ok=True)
    stat = os.stat(path)
    key = f"{asset_id}.{stat.st_mtime_ns}-{stat.st_size}"
    for ext in ("png", "jpg"):
        cached = os.path.join(folder, f"{key}.{ext}")
        if os.path.isfile(cached):
            return cached
    with Image.open(path, formats=tuple(FORMATS)) as img:
        img.draft("RGB", (THUMB_SIDE * 2, THUMB_SIDE * 2))  # JPEG: decode at a fraction of full size
        thumb = ImageOps.exif_transpose(img)  # as wallrender draws it
    alpha = thumb.mode in ("RGBA", "LA", "PA") or "transparency" in thumb.info
    thumb = thumb.convert("RGBA" if alpha else "RGB")
    thumb.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.LANCZOS)
    ext = "png" if alpha else "jpg"
    cached = os.path.join(folder, f"{key}.{ext}")
    partial = f"{cached}.{os.getpid()}.{time.time_ns()}.part"
    if alpha:
        thumb.save(partial, "PNG", optimize=True)
    else:
        thumb.save(partial, "JPEG", quality=THUMB_JPEG_QUALITY)
    os.replace(partial, cached)  # another request making the same one is harmless
    for name in os.listdir(folder):  # older thumbnails of this id
        if name.startswith(f"{asset_id}.") and name != os.path.basename(cached) and not name.endswith(".part"):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass
    return cached


@template_bp.route("/assets/<asset_id>/thumb", methods=["GET"])
def serve_thumb(asset_id):
    path = _asset_path(asset_id)
    if not path:
        return jsonify({"error": GONE}), 404
    try:
        return send_file(_thumb_path(asset_id, path))
    except (OSError, Image.DecompressionBombError):
        return jsonify({"error": "That asset is not a readable image."}), 404


@template_bp.route("/assets/<asset_id>", methods=["DELETE"])
def delete_asset(asset_id):
    path = _asset_path(asset_id)
    if not path:
        return jsonify({"error": GONE}), 404
    _empty_trash()
    _to_trash(path, _trash())
    return "", 204


@template_bp.route("/assets/<asset_id>/restore", methods=["POST"])
def restore_asset(asset_id):
    """Move an asset back from the trash. By default that is the copy a
    replace pushed out (the library's own version from before), else the
    deleted copy; ?from=deleted (Undo after Delete) takes only the deleted
    copy. An asset uploaded under the same id since is never overwritten."""
    _empty_trash()
    if request.args.get("from") == "deleted":
        kept = _trashed_path(asset_id)
    else:
        kept = _trashed_path(asset_id, _replaced()) or _trashed_path(asset_id)
    if not kept:
        return jsonify({"error": f"Nothing to undo: {asset_id} is no longer in the trash."}), 404
    if _asset_path(asset_id):
        return jsonify({"error": f"Not restored: a newer {asset_id} is in the library."}), 409
    path = os.path.join(_folder(), f"{asset_id}{os.path.splitext(kept)[1]}")
    shutil.move(kept, path)
    return jsonify(_image_info(asset_id, path))


# --- Export and import: the bundle Brander uses ---------------------------


def _slug(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")[:64] or "template"


def asset_ids(template):
    ids = []
    background = template.get("background") or {}
    if background.get("asset"):
        ids.append(background["asset"])
    ids += [layer["asset"] for layer in template.get("layers", []) if layer.get("type") == "image"]
    roles = template.get("roles") or {}
    variants = list((roles.get("variants") or {}).values()) + [roles.get(k) or {} for k in ("empty", "default")]
    ids += [v["background"]["asset"] for v in variants if (v.get("background") or {}).get("asset")]
    return list(dict.fromkeys(ids))


README = """This is a Brander wallpaper template made in EWOK.

1. Copy every file here into Brander's assets folder on the JAWA server
   (the template's "Assets directory" setting).
2. Set the Brander template's "Wallpaper template" setting to {name}.json
   (or name it in a template set file).
"""


@template_bp.route("/export", methods=["POST"])
def export_bundle():
    body = _json_body()
    template = body.get("template") if isinstance(body, dict) else None
    problems = validate(template)
    if problems:
        return jsonify({"problems": problems}), 400
    missing = [i for i in asset_ids(template) if not _asset_path(i)]
    if missing:
        return jsonify({"problems": [f"asset {i!r} is not in the library" for i in missing]}), 422
    name = _slug(template.get("name"))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(f"{name}.json", json.dumps(template, indent=2) + "\n")
        for asset_id in asset_ids(template):
            path = _asset_path(asset_id)
            bundle.write(path, os.path.basename(path))
        bundle.writestr("README.txt", README.format(name=name))
    buffer.seek(0)
    return send_file(buffer, mimetype="application/zip", as_attachment=True,
                     download_name=f"{name}.zip")


@template_bp.route("/package", methods=["POST"])
def export_package():
    """The template as a .brander.json package for JAWA's template store:
    one JSON file, assets inside as base64, nothing to unpack."""
    body = _json_body()
    template = body.get("template") if isinstance(body, dict) else None
    problems = validate(template)
    if problems:
        return jsonify({"problems": problems}), 400
    missing = [i for i in asset_ids(template) if not _asset_path(i)]
    if missing:
        return jsonify({"problems": [f"asset {i!r} is not in the library" for i in missing]}), 422
    assets = {}
    for asset_id in asset_ids(template):
        with open(_asset_path(asset_id), "rb") as handle:
            assets[asset_id] = base64.b64encode(handle.read()).decode("ascii")
    name = template.get("name") or "Untitled template"
    # The store can refuse a template its vendored wallrender cannot render.
    package = {"kind": "brander-template", "format": 1, "name": name,
               "wallrender": wallrender.__version__, "requires_wallrender": required_version(template),
               "template": template, "assets": assets}
    data = io.BytesIO((json.dumps(package, indent=1) + "\n").encode())
    response = send_file(data, mimetype="application/json", as_attachment=True,
                         download_name=f"{_slug(name)}.brander.json")
    response.headers["X-Template-SHA256"] = template_sha256(template)
    return response


def template_sha256(template):
    """The digest JAWA's template store shows for this upload: it hashes the
    template.json it writes, the template dumped with indent 2 and a newline
    (brander_store.save_version), not the package file."""
    return hashlib.sha256((json.dumps(template, indent=2) + "\n").encode()).hexdigest()


def _load_template(raw):
    try:
        template = json.loads(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None, ["the template is not valid JSON"]
    problems = validate(template)
    return (None, problems) if problems else (template, [])


def _os_litter(path):
    """Files an operating system adds when it zips a folder: macOS's
    __MACOSX/ AppleDouble copies (._name), .DS_Store, and Windows' Thumbs.db.
    A bundle re-zipped in Finder would otherwise hold a second .json."""
    parts = path.replace("\\", "/").split("/")
    name = parts[-1]
    return "__MACOSX" in parts or name.startswith("._") or name in (".DS_Store", "Thumbs.db")


@template_bp.route("/import", methods=["POST"])
def import_bundle():
    upload = request.files.get("file")
    if not upload:
        return jsonify({"error": "No file provided."}), 400
    data = upload.read()
    if (upload.filename or "").lower().endswith(".json"):
        try:
            parsed = json.loads(data)
        except (ValueError, UnicodeDecodeError, RecursionError):
            parsed = None
        if isinstance(parsed, dict) and parsed.get("kind") == "brander-template":
            return _import_package(parsed)
        template, problems = _load_template(data)
        if problems:
            return jsonify({"error": "That template cannot be used.", "problems": problems}), 400
        return jsonify({"template": template, "assets": []})
    if not zipfile.is_zipfile(io.BytesIO(data)):
        return jsonify({"error": "Open a template .json or an EWOK .zip bundle."}), 400
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            entries = [e for e in bundle.infolist() if not e.is_dir() and not _os_litter(e.filename)]
            if len(entries) > MAX_BUNDLE_ENTRIES or sum(e.file_size for e in entries) > MAX_BUNDLE_BYTES:
                return jsonify({"error": "That bundle is too large."}), 400
            jsons = [e for e in entries if e.filename.lower().endswith(".json")]
            if len(jsons) != 1:
                return jsonify({"error": "A bundle must hold exactly one template .json."}), 400
            template, problems = _load_template(bundle.read(jsons[0]))
            if problems:
                return jsonify({"error": "That template cannot be used.", "problems": problems}), 400
            images = {}
            for entry in entries:
                # Only the file name counts: entry paths never reach the disk.
                name = os.path.basename(entry.filename.replace("\\", "/"))
                stem, ext = os.path.splitext(name)
                if ext.lower().lstrip(".") in EXTENSIONS:
                    images[name] = (stem, entry)
            found = {stem: (name, bundle.read(entry)) for name, (stem, entry) in images.items()}
    except (zipfile.BadZipFile, OSError, EOFError):
        return jsonify({"error": "That bundle is damaged and cannot be read."}), 400
    return _store_imported(template, found)


def _store_imported(template, found):
    """Keep only the assets the template uses (so a bundle cannot quietly
    replace unrelated library assets). A different file under an id the
    library already has is a conflict: without replace=yes or replace=no
    the answer is a 409 naming them, and nothing is written. replace=no
    keeps the library's copies; replace=yes moves them to the trash."""
    used = set(asset_ids(template))
    choice = request.form.get("replace")
    usable, skipped = {}, []
    for asset_id, (name, data) in found.items():
        if asset_id not in used:
            skipped.append(f"{name}: not used by the template")
        elif not ASSET_ID.fullmatch(asset_id):
            skipped.append(f"{name}: not a valid asset id")
        else:
            usable[asset_id] = (name, data)
    conflicts = sorted(
        asset_id for asset_id, (_, data) in usable.items()
        if (path := _asset_path(asset_id)) and not _same_bytes(path, data)
        and not isinstance(_check_asset(data), str))
    if conflicts and choice not in ("yes", "no"):
        return jsonify({"error": "That template has assets with the same ids as library assets.",
                        "conflicts": conflicts}), 409
    added, replaced, kept = [], [], []
    for asset_id, (name, data) in usable.items():
        if asset_id in conflicts and choice == "no":
            kept.append(asset_id)
            continue
        stored, error = _store_asset(asset_id, data)
        if error:
            skipped.append(f"{name}: {error}")
            continue
        added.append(stored["id"])
        if asset_id in conflicts:
            replaced.append(asset_id)
    return jsonify({"template": template, "assets": added, "replaced": replaced,
                    "kept": kept, "skipped": skipped})


def _import_package(package):
    """Open a .brander.json: its template, and the assets it uses."""
    template, problems = _load_template(json.dumps(package.get("template")))
    if problems:
        return jsonify({"error": "That template cannot be used.", "problems": problems}), 400
    assets = package.get("assets")
    if not isinstance(assets, dict) or len(assets) > MAX_BUNDLE_ENTRIES:
        return jsonify({"error": "That package's assets are not usable."}), 400
    found, bad = {}, []
    for asset_id, encoded in assets.items():
        try:
            found[str(asset_id)] = (str(asset_id), base64.b64decode(encoded, validate=True))
        except (ValueError, TypeError):
            bad.append(f"{asset_id}: not valid base64")
    response = _store_imported(template, found)
    if isinstance(response, tuple):
        return response  # the 409: nothing was written
    body = response.get_json()
    body["skipped"] = bad + body["skipped"]
    return jsonify(body)
