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

    def test_process_path_traversal_blocked(self, client):
        resp = client.post(
            "/api/process",
            data=json.dumps({"filename": "../../etc/passwd"}),
            content_type="application/json",
        )
        assert resp.status_code == 404


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
