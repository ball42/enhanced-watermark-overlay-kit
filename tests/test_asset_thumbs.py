"""The asset library shows small thumbnails, made once, never the originals."""

import io
import os
import random
from unittest import mock

import pytest
from PIL import Image

import config
from views import template_api


def photo_bytes(size=(1290, 2796), fmt="JPEG", mode="RGB"):
    """A grainy photo-sized image, so the original is megabytes."""
    rng = random.Random(1)
    small = Image.frombytes(mode, (size[0] // 8, size[1] // 8),
                            bytes(rng.randrange(256) for _ in range(size[0] // 8 * size[1] // 8 * len(mode))))
    buffer = io.BytesIO()
    small.resize(size, Image.NEAREST).save(buffer, fmt, **({"quality": 97} if fmt == "JPEG" else {}))
    return buffer.getvalue()


def upload(client, data, name):
    return client.post("/api/template/assets", data={"file": (io.BytesIO(data), name)},
                       content_type="multipart/form-data")


def thumb(client, asset_id):
    resp = client.get(f"/api/template/assets/{asset_id}/thumb")
    assert resp.status_code == 200
    return resp, Image.open(io.BytesIO(resp.data))


def test_a_photo_thumbnail_is_a_small_jpeg_of_at_most_96_px(client):
    original = photo_bytes()
    assert upload(client, original, "photo.jpg").status_code == 201
    resp, img = thumb(client, "photo")
    assert resp.mimetype == "image/jpeg"
    assert max(img.size) == 96 and img.size == (44, 96)  # keeps the 1290x2796 shape
    assert len(resp.data) < 12_000 < len(original) // 100
    # The original is still served whole, for rendering and Download.
    assert client.get("/api/template/assets/photo").data == original


def test_a_logo_with_transparency_keeps_it_as_a_png(client):
    upload(client, photo_bytes((400, 200), "PNG", "RGBA"), "logo.png")
    resp, img = thumb(client, "logo")
    assert resp.mimetype == "image/png" and img.mode == "RGBA" and img.size == (96, 48)


def test_a_small_asset_is_not_scaled_up(client):
    upload(client, photo_bytes((40, 24)), "dot.jpg")
    assert thumb(client, "dot")[1].size == (40, 24)


def test_a_thumbnail_is_made_once_and_remade_after_a_replace(client):
    upload(client, photo_bytes((800, 400)), "wide.jpg")
    with mock.patch.object(template_api.ImageOps, "exif_transpose", wraps=template_api.ImageOps.exif_transpose) as made:
        first = thumb(client, "wide")[1].size
        for _ in range(5):
            thumb(client, "wide")
        assert made.call_count == 1  # the budget: one decode per asset version, not one per page load
        upload(client, photo_bytes((400, 800)), "wide.jpg")  # a different photo under the same id
        assert thumb(client, "wide")[1].size == (48, 96) != first
        assert made.call_count == 2
    kept = os.listdir(os.path.join(config.TEMPLATE_ASSETS_FOLDER, template_api.THUMBS))
    assert len(kept) == 1 and kept[0].startswith("wide.")  # the old thumbnail is gone


def test_a_revalidated_thumbnail_answers_304(client):
    upload(client, photo_bytes((300, 300)), "sq.jpg")
    etag = thumb(client, "sq")[0].headers["ETag"]
    again = client.get("/api/template/assets/sq/thumb", headers={"If-None-Match": etag})
    assert again.status_code == 304


def test_the_thumbnail_folder_is_not_in_the_library(client):
    upload(client, photo_bytes((300, 300)), "sq.jpg")
    thumb(client, "sq")
    assert [a["id"] for a in client.get("/api/template/assets").get_json()["assets"]] == ["sq"]


def test_a_deleted_asset_has_no_thumbnail(client):
    upload(client, photo_bytes((300, 300)), "sq.jpg")
    client.delete("/api/template/assets/sq")
    assert client.get("/api/template/assets/sq/thumb").status_code == 404


@pytest.mark.parametrize("asset_id", ["..", "%2e%2e%2fconfig", "UPPER", ".thumbs"])
def test_thumbnails_reject_odd_ids(client, asset_id):
    assert client.get(f"/api/template/assets/{asset_id}/thumb").status_code == 404


def test_a_corrupt_file_in_the_library_is_404_not_500(client):
    path = os.path.join(config.TEMPLATE_ASSETS_FOLDER, "broken.png")
    os.makedirs(config.TEMPLATE_ASSETS_FOLDER, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"not a png")
    assert client.get("/api/template/assets/broken/thumb").status_code == 404
