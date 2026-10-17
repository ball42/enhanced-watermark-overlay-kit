"""Tests for API endpoints: upload, process, download, preview."""

import json
import os

import pytest
from tests.conftest import make_test_image


# ── Upload ─────────────────────────────────────


class TestUpload:
    def test_upload_valid_png(self, client):
        img = make_test_image()
        resp = client.post(
            "/api/upload",
            data={"file": (img, "photo.png")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert data["dimensions"]["width"] == 100
        assert data["dimensions"]["height"] == 100
        assert data["filename"].endswith("_photo.png")

    def test_upload_no_file(self, client):
        resp = client.post("/api/upload", data={}, content_type="multipart/form-data")
        assert resp.status_code == 400
        assert "No file provided" in resp.get_json()["error"]

    def test_upload_invalid_extension(self, client):
        import io

        buf = io.BytesIO(b"not an image")
        resp = client.post(
            "/api/upload",
            data={"file": (buf, "malware.exe")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400
        assert "Invalid file type" in resp.get_json()["error"]


# ── Process ────────────────────────────────────


class TestProcess:
    def _upload(self, client):
        """Helper: upload an image and return its filename."""
        img = make_test_image()
        resp = client.post(
            "/api/upload",
            data={"file": (img, "sample.png")},
            content_type="multipart/form-data",
        )
        return resp.get_json()["filename"]

    def test_process_basic(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": filename}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["success"] is True
        assert "processed_filename" in data

    def test_process_with_opacity(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": filename, "opacity": 50}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert data["success"] is True

    def test_process_with_text_overlay(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({
                "filename": filename,
                "text_overlays": [
                    {"text": "Hello", "x": "50%", "y": "50%", "size": 24, "color": "#FF0000"}
                ],
            }),
            content_type="application/json",
        )
        data = resp.get_json()
        assert data["success"] is True

    def test_process_with_wallpaper(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({
                "filename": filename,
                "wallpaper_mode": True,
                "wallpaper_preset": "iPhone 15 Pro",
                "fit_mode": "fit",
            }),
            content_type="application/json",
        )
        data = resp.get_json()
        assert data["success"] is True
        assert data["dimensions"]["width"] == 1179
        assert data["dimensions"]["height"] == 2556

    def test_process_missing_file(self, client):
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": "nonexistent.png"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_process_with_text_alignment(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({
                "filename": filename,
                "text_overlays": [
                    {"text": "Right", "x": "80%", "y": "50%", "size": 24,
                     "color": "#FF0000", "alignment": "right"}
                ],
            }),
            content_type="application/json",
        )
        assert resp.get_json()["success"] is True

    def test_process_with_size_percent(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({
                "filename": filename,
                "text_overlays": [
                    {"text": "Big", "x": "50%", "y": "50%", "size_percent": 10,
                     "color": "#FFFFFF"}
                ],
            }),
            content_type="application/json",
        )
        assert resp.get_json()["success"] is True

    def test_process_jpeg_output(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": filename, "output_format": "jpeg"}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert data["success"] is True
        assert data["processed_filename"].endswith(".jpg")

    def test_process_webp_output(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": filename, "output_format": "webp"}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert data["success"] is True
        assert data["processed_filename"].endswith(".webp")

    def test_process_path_traversal_blocked(self, client):
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": "../../etc/passwd"}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    # ── Area 1: Image adjustments ──────────────

    def test_process_with_brightness(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": filename, "brightness": 150}),
            content_type="application/json",
        )
        assert resp.get_json()["success"] is True

    def test_process_with_contrast(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": filename, "contrast": 50}),
            content_type="application/json",
        )
        assert resp.get_json()["success"] is True

    def test_process_with_blur(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": filename, "blur_sharpen": 10}),
            content_type="application/json",
        )
        assert resp.get_json()["success"] is True

    def test_process_with_sharpen(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": filename, "blur_sharpen": 90}),
            content_type="application/json",
        )
        assert resp.get_json()["success"] is True

    def test_process_with_rotation(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": filename, "rotation": 90}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert data["success"] is True
        # 90° rotation of 100x100 → still 100x100
        assert data["dimensions"]["width"] == 100
        assert data["dimensions"]["height"] == 100

    def test_process_with_rotation_45(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": filename, "rotation": 45}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert data["success"] is True
        # 45° rotation with expand=True increases dimensions
        assert data["dimensions"]["width"] > 100
        assert data["dimensions"]["height"] > 100

    # ── Area 2: Font + text opacity ────────────

    def test_process_text_with_font_family(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({
                "filename": filename,
                "text_overlays": [
                    {"text": "Serif", "x": "50%", "y": "50%", "size": 24,
                     "color": "#FFFFFF", "font_family": "Times New Roman"}
                ],
            }),
            content_type="application/json",
        )
        assert resp.get_json()["success"] is True

    def test_process_text_with_opacity(self, client):
        filename = self._upload(client)
        resp = client.post(
            "/api/process",
            data=json.dumps({
                "filename": filename,
                "text_overlays": [
                    {"text": "Faded", "x": "50%", "y": "50%", "size": 24,
                     "color": "#FF0000", "text_opacity": 50}
                ],
            }),
            content_type="application/json",
        )
        assert resp.get_json()["success"] is True

    # ── Area 3: Image overlays ─────────────────

    def test_process_with_image_overlay(self, client):
        # Upload main image
        filename = self._upload(client)
        # Upload overlay image
        overlay_img = make_test_image(50, 50, color=(0, 255, 0))
        resp = client.post(
            "/api/upload",
            data={"file": (overlay_img, "overlay.png")},
            content_type="multipart/form-data",
        )
        overlay_filename = resp.get_json()["filename"]

        resp = client.post(
            "/api/process",
            data=json.dumps({
                "filename": filename,
                "image_overlays": [
                    {"filename": overlay_filename, "x": 10, "y": 10,
                     "width": 30, "height": 30, "opacity": 80}
                ],
            }),
            content_type="application/json",
        )
        assert resp.get_json()["success"] is True

    def test_process_with_image_overlay_no_size(self, client):
        filename = self._upload(client)
        overlay_img = make_test_image(50, 50, color=(0, 0, 255))
        resp = client.post(
            "/api/upload",
            data={"file": (overlay_img, "overlay2.png")},
            content_type="multipart/form-data",
        )
        overlay_filename = resp.get_json()["filename"]

        resp = client.post(
            "/api/process",
            data=json.dumps({
                "filename": filename,
                "image_overlays": [
                    {"filename": overlay_filename, "x": 0, "y": 0, "opacity": 100}
                ],
            }),
            content_type="application/json",
        )
        assert resp.get_json()["success"] is True

    def test_process_with_image_overlay_percent_size(self, client):
        """Image overlay with percentage-based width/height."""
        filename = self._upload(client)
        overlay_img = make_test_image(50, 50, color=(0, 128, 0))
        resp = client.post(
            "/api/upload",
            data={"file": (overlay_img, "overlay_pct.png")},
            content_type="multipart/form-data",
        )
        overlay_filename = resp.get_json()["filename"]

        resp = client.post(
            "/api/process",
            data=json.dumps({
                "filename": filename,
                "image_overlays": [
                    {"filename": overlay_filename, "x": "10%", "y": "10%",
                     "width": "50%", "height": "50%", "opacity": 100}
                ],
            }),
            content_type="application/json",
        )
        assert resp.get_json()["success"] is True

    def test_process_with_image_overlay_width_only(self, client):
        """Image overlay with only width specified preserves aspect ratio."""
        filename = self._upload(client)
        overlay_img = make_test_image(80, 40, color=(128, 0, 128))
        resp = client.post(
            "/api/upload",
            data={"file": (overlay_img, "overlay_w.png")},
            content_type="multipart/form-data",
        )
        overlay_filename = resp.get_json()["filename"]

        resp = client.post(
            "/api/process",
            data=json.dumps({
                "filename": filename,
                "image_overlays": [
                    {"filename": overlay_filename, "x": 0, "y": 0, "width": "25%"}
                ],
            }),
            content_type="application/json",
        )
        assert resp.get_json()["success"] is True


# ── Download ───────────────────────────────────


class TestDownload:
    def _process(self, client):
        """Helper: upload + process, return processed filename."""
        img = make_test_image()
        resp = client.post(
            "/api/upload",
            data={"file": (img, "dl.png")},
            content_type="multipart/form-data",
        )
        filename = resp.get_json()["filename"]
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": filename}),
            content_type="application/json",
        )
        return resp.get_json()["processed_filename"]

    def test_download_valid(self, client):
        processed = self._process(client)
        resp = client.get(f"/api/download/{processed}")
        assert resp.status_code == 200
        assert resp.content_type in ("image/png", "application/octet-stream")

    def test_download_nonexistent(self, client):
        resp = client.get("/api/download/does_not_exist.png")
        assert resp.status_code == 404

    def test_download_path_traversal_blocked(self, client):
        resp = client.get("/api/download/../../etc/passwd")
        assert resp.status_code == 404


# ── Preview ────────────────────────────────────


class TestPreview:
    def test_preview_processed(self, client):
        img = make_test_image()
        resp = client.post(
            "/api/upload",
            data={"file": (img, "prev.png")},
            content_type="multipart/form-data",
        )
        filename = resp.get_json()["filename"]
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": filename}),
            content_type="application/json",
        )
        processed = resp.get_json()["processed_filename"]
        resp = client.get(f"/api/preview/{processed}")
        assert resp.status_code == 200

    def test_preview_original(self, client):
        img = make_test_image()
        resp = client.post(
            "/api/upload",
            data={"file": (img, "orig.png")},
            content_type="multipart/form-data",
        )
        filename = resp.get_json()["filename"]
        resp = client.get(f"/api/original/{filename}")
        assert resp.status_code == 200

    def test_preview_path_traversal_blocked(self, client):
        resp = client.get("/api/original/../../etc/passwd")
        assert resp.status_code == 404


# ── Upload expiry ──────────────────────────────


class TestUploadExpiry:
    """Cleanup removes files an hour after their last use, not their upload."""

    def _upload(self, client):
        resp = client.post("/api/upload", data={"file": (make_test_image(), "old.png")},
                           content_type="multipart/form-data")
        return resp.get_json()["filename"]

    def _age(self, path, minutes):
        import time
        then = time.time() - minutes * 60
        os.utime(path, (then, then))

    def _cleanup(self, monkeypatch, folder):
        from utils import cleanup
        monkeypatch.setattr(cleanup, "_last_cleanup", 0)
        cleanup.cleanup_old_files(folder)

    def test_processing_keeps_an_upload_in_use(self, app, client, monkeypatch):
        import time
        filename = self._upload(client)
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        self._age(path, 50)
        assert client.post("/api/process", json={"filename": filename}).status_code == 200
        assert time.time() - os.path.getmtime(path) < 60
        self._cleanup(monkeypatch, app.config["UPLOAD_FOLDER"])
        assert os.path.exists(path)

    def test_previews_and_overlays_count_as_use(self, app, client):
        import time
        filename = self._upload(client)
        logo = self._upload(client)
        for name in (filename, logo):
            self._age(os.path.join(app.config["UPLOAD_FOLDER"], name), 50)
        resp = client.post("/api/process", json={
            "filename": filename, "image_overlays": [{"filename": logo, "x": 0, "y": 0}]})
        processed = resp.get_json()["processed_filename"]
        assert time.time() - os.path.getmtime(os.path.join(app.config["UPLOAD_FOLDER"], logo)) < 60
        out = os.path.join(app.config["TEMP_FOLDER"], processed)
        self._age(out, 50)
        assert client.get(f"/api/preview/{processed}").status_code == 200
        assert time.time() - os.path.getmtime(out) < 60

    def test_an_expired_upload_says_so(self, app, client, monkeypatch):
        filename = self._upload(client)
        self._age(os.path.join(app.config["UPLOAD_FOLDER"], filename), 61)
        self._cleanup(monkeypatch, app.config["UPLOAD_FOLDER"])
        resp = client.post("/api/process", json={"filename": filename})
        assert resp.status_code == 410
        assert "expired" in resp.get_json()["error"]
        assert "Upload it again" in resp.get_json()["error"]


# ── A new render replaces the previous result ──


class TestPreviousResult:
    def _upload(self, client):
        resp = client.post(
            "/api/upload",
            data={"file": (make_test_image(), "live.png")},
            content_type="multipart/form-data",
        )
        return resp.get_json()["filename"]

    def _process(self, client, filename, **extra):
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": filename, **extra}),
            content_type="application/json",
        )
        assert resp.status_code == 200, resp.get_json()
        return resp.get_json()["processed_filename"]

    def test_process_removes_the_previous_processed_file(self, app, client):
        temp = app.config["TEMP_FOLDER"]
        filename = self._upload(client)
        first = self._process(client, filename)
        assert os.path.exists(os.path.join(temp, first))
        second = self._process(client, filename, previous_filename=first)
        assert not os.path.exists(os.path.join(temp, first))
        assert os.path.exists(os.path.join(temp, second))

    def test_previous_filename_never_removes_other_files(self, app, client):
        filename = self._upload(client)
        upload_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        outside = os.path.join(os.path.dirname(app.config["TEMP_FOLDER"]), "processed_keep.png")
        with open(outside, "wb") as f:
            f.write(b"x")
        for previous in (filename, "../processed_keep.png", f"../uploads/{filename}", 42):
            self._process(client, filename, previous_filename=previous)
        assert os.path.exists(upload_path)
        assert os.path.exists(outside)
