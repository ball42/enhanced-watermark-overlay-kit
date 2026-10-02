"""Template mode API: render previews through wallrender, and keep the
library of template assets (backgrounds and logos) by asset id.

Everything here is local-only like the rest of EWOK, but templates and
uploads are still treated as untrusted: wallrender bounds the render,
asset ids follow wallrender's pattern, and only PNG and JPEG are kept.
"""

import base64
import io
import json
import os
import re
import zipfile

from flask import Blueprint, abort, jsonify, request, send_file
from PIL import Image, UnidentifiedImageError

import config
from wallrender import TemplateError, lint, render, validate
from wallrender.cli import folder_assets, stress_values
from wallrender.devices import fit_warnings
from wallrender.schema import ASSET_ID, MAX_PIXELS, MAX_SIDE

template_bp = Blueprint("template_api", __name__, url_prefix="/api/template")

FORMATS = {"PNG": "png", "JPEG": "jpg"}
EXTENSIONS = ("png", "jpg", "jpeg")
MAX_BUNDLE_ENTRIES = 60
MAX_BUNDLE_BYTES = 64 * 1024 * 1024  # uncompressed, checked before reading


def _folder():
    os.makedirs(config.TEMPLATE_ASSETS_FOLDER, exist_ok=True)
    return config.TEMPLATE_ASSETS_FOLDER


def _png_data_url(image):
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _render_one(template, values, assets, label, devices=(), screen="lock"):
    image = render(template, values, assets)
    return {"label": label, "image": _png_data_url(image),
            "warnings": lint(template, values, assets),
            "device_warnings": fit_warnings(template, image.size, list(devices), screen)}


@template_bp.route("/preview", methods=["POST"])
def preview():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("values"), dict) \
            or "template" not in body:
        return jsonify({"error": "Send JSON with a template and a values object."}), 400
    template, values = body["template"], body["values"]
    devices = body.get("devices") or []
    screen = body.get("screen", "lock")
    if screen not in ("lock", "home") or not isinstance(devices, list) \
            or not all(isinstance(d, str) for d in devices):
        return jsonify({"error": "devices must be a list of ids and screen lock or home."}), 400
    problems = validate(template)
    if problems:
        return jsonify({"problems": problems}), 400
    assets = folder_assets(_folder())
    variants = [("sample", values)]
    if body.get("stress"):
        variants += [("long", stress_values(template)), ("empty", {})]
    try:
        renders = [_render_one(template, v, assets, label, devices if label == "sample" else (), screen)
                   for label, v in variants]
    except TemplateError as err:
        return jsonify({"problems": err.problems}), 422
    return jsonify({"renders": renders})


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


@template_bp.route("/assets", methods=["GET"])
def list_assets():
    assets = []
    for name in sorted(os.listdir(_folder())):
        asset_id, ext = os.path.splitext(name)
        if ext.lstrip(".") in EXTENSIONS and ASSET_ID.fullmatch(asset_id):
            with Image.open(os.path.join(_folder(), name)) as img:
                assets.append({"id": asset_id, "width": img.width, "height": img.height})
    return jsonify({"assets": assets})


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


def _store_asset(asset_id, data):
    """Keep data as <id>.png or .jpg if it really is a PNG or JPEG within
    wallrender's limits. Returns (info, None) or (None, error)."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt, width, height = img.format, img.width, img.height
            img.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return None, "That file is not a readable image."
    if fmt not in FORMATS:
        return None, "Assets must be PNG or JPEG."
    if max(width, height) > MAX_SIDE or width * height > MAX_PIXELS:
        return None, f"Assets are limited to {MAX_SIDE}px per side."
    old = _asset_path(asset_id)
    if old:
        os.remove(old)
    with open(os.path.join(_folder(), f"{asset_id}.{FORMATS[fmt]}"), "wb") as handle:
        handle.write(data)
    return {"id": asset_id, "width": width, "height": height}, None


@template_bp.route("/assets/<asset_id>", methods=["GET"])
def serve_asset(asset_id):
    path = _asset_path(asset_id)
    if not path:
        abort(404)
    return send_file(path)


@template_bp.route("/assets/<asset_id>", methods=["DELETE"])
def delete_asset(asset_id):
    path = _asset_path(asset_id)
    if not path:
        abort(404)
    os.remove(path)
    return "", 204


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
    body = request.get_json(silent=True)
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


def _load_template(raw):
    try:
        template = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None, ["the template is not valid JSON"]
    problems = validate(template)
    return (None, problems) if problems else (template, [])


@template_bp.route("/import", methods=["POST"])
def import_bundle():
    upload = request.files.get("file")
    if not upload:
        return jsonify({"error": "No file provided."}), 400
    data = upload.read()
    if (upload.filename or "").lower().endswith(".json"):
        template, problems = _load_template(data)
        if problems:
            return jsonify({"error": "That template cannot be used.", "problems": problems}), 400
        return jsonify({"template": template, "assets": []})
    if not zipfile.is_zipfile(io.BytesIO(data)):
        return jsonify({"error": "Open a template .json or an EWOK .zip bundle."}), 400
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        entries = [e for e in bundle.infolist() if not e.is_dir()]
        if len(entries) > MAX_BUNDLE_ENTRIES or sum(e.file_size for e in entries) > MAX_BUNDLE_BYTES:
            return jsonify({"error": "That bundle is too large."}), 400
        jsons = [e for e in entries if e.filename.lower().endswith(".json")]
        if len(jsons) != 1:
            return jsonify({"error": "A bundle must hold exactly one template .json."}), 400
        template, problems = _load_template(bundle.read(jsons[0]))
        if problems:
            return jsonify({"error": "That template cannot be used.", "problems": problems}), 400
        added, skipped = [], []
        for entry in entries:
            # Only the file name counts: entry paths never reach the disk.
            name = os.path.basename(entry.filename.replace("\\", "/"))
            stem, ext = os.path.splitext(name)
            if ext.lower().lstrip(".") not in EXTENSIONS:
                continue
            if not ASSET_ID.fullmatch(stem):
                skipped.append(f"{name}: not a valid asset id")
                continue
            stored, error = _store_asset(stem, bundle.read(entry))
            if error:
                skipped.append(f"{name}: {error}")
            else:
                added.append(stored["id"])
    return jsonify({"template": template, "assets": added, "skipped": skipped})
