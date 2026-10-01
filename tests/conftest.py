"""Shared fixtures for EWOK tests."""

import io
import os
import shutil
import tempfile

import pytest
from PIL import Image

from app_factory import create_app


@pytest.fixture()
def app(tmp_path):
    """Create a Flask app with isolated temp directories."""
    upload_dir = str(tmp_path / "uploads")
    temp_dir = str(tmp_path / "temp")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    # Patch config before creating app
    import config
    orig_upload = config.UPLOAD_FOLDER
    orig_temp = config.TEMP_FOLDER
    config.UPLOAD_FOLDER = upload_dir
    config.TEMP_FOLDER = temp_dir

    application = create_app()
    application.config["TESTING"] = True
    application.config["UPLOAD_FOLDER"] = upload_dir

    yield application

    # Restore original config
    config.UPLOAD_FOLDER = orig_upload
    config.TEMP_FOLDER = orig_temp


@pytest.fixture()
def client(app):
    """Flask test client."""
    return app.test_client()


def make_test_image(width=100, height=100, color=(255, 0, 0), fmt="PNG"):
    """Create an in-memory test image and return as BytesIO."""
    img = Image.new("RGBA", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    buf.name = f"test.{fmt.lower()}"
    return buf
