"""Template mode API: render previews through wallrender, and keep the
library of template assets (backgrounds and logos) by asset id.

Everything here is local-only like the rest of EWOK, but templates and
uploads are still treated as untrusted: wallrender bounds the render,
asset ids follow wallrender's pattern, and only PNG and JPEG are kept.
"""

import base64
import io
import os
import re

from flask import Blueprint, abort, jsonify, request, send_file
from PIL import Image, UnidentifiedImageError

import config
from wallrender import TemplateError, lint, render, validate
from wallrender.cli import folder_assets, stress_values
from wallrender.schema import ASSET_ID, MAX_PIXELS, MAX_SIDE

template_bp = Blueprint("template_api", __name__, url_prefix="/api/template")

FORMATS = {"PNG": "png", "JPEG": "jpg"}
EXTENSIONS = ("png", "jpg", "jpeg")


def _folder():
    os.makedirs(config.TEMPLATE_ASSETS_FOLDER, exist_ok=True)
    return config.TEMPLATE_ASSETS_FOLDER


def _png_data_url(image):
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _render_one(template, values, assets, label):
    image = render(template, values, assets)
    return {"label": label, "image": _png_data_url(image),
            "warnings": lint(template, values, assets)}


@template_bp.route("/preview", methods=["POST"])
def preview():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("values"), dict) \
            or "template" not in body:
        return jsonify({"error": "Send JSON with a template and a values object."}), 400
    template, values = body["template"], body["values"]
    problems = validate(template)
    if problems:
        return jsonify({"problems": problems}), 400
    assets = folder_assets(_folder())
    variants = [("sample", values)]
    if body.get("stress"):
        variants += [("long", stress_values(template)), ("empty", {})]
    try:
        renders = [_render_one(template, v, assets, label) for label, v in variants]
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
    data = upload.read()
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt, width, height = img.format, img.width, img.height
            img.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        return jsonify({"error": "That file is not a readable image."}), 400
    if fmt not in FORMATS:
        return jsonify({"error": "Assets must be PNG or JPEG."}), 400
    if max(width, height) > MAX_SIDE or width * height > MAX_PIXELS:
        return jsonify({"error": f"Assets are limited to {MAX_SIDE}px per side."}), 400
    old = _asset_path(asset_id)
    if old:
        os.remove(old)
    with open(os.path.join(_folder(), f"{asset_id}.{FORMATS[fmt]}"), "wb") as handle:
        handle.write(data)
    return jsonify({"id": asset_id, "width": width, "height": height}), 201


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
