"""EWOK runs as a local tool: localhost only, debug off, no CORS."""

import importlib
import os

import pytest


def test_debug_is_off_by_default(monkeypatch):
    monkeypatch.delenv("EWOK_DEBUG", raising=False)
    import config

    assert importlib.reload(config).DEBUG is False


def test_debug_can_be_turned_on(monkeypatch):
    monkeypatch.setenv("EWOK_DEBUG", "1")
    import config

    assert importlib.reload(config).DEBUG is True
    monkeypatch.delenv("EWOK_DEBUG")
    importlib.reload(config)


def test_no_cors_headers(client):
    resp = client.get("/", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in resp.headers


def test_data_folders_do_not_depend_on_the_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    import config

    config = importlib.reload(config)
    root = os.path.dirname(os.path.abspath(config.__file__))
    assert config.UPLOAD_FOLDER == os.path.join(root, "static", "uploads")
    assert config.TEMP_FOLDER == os.path.join(root, "temp")


def test_entry_point_serves_on_localhost(monkeypatch):
    import app as ewok_app

    seen = {}
    monkeypatch.setattr(
        ewok_app.app, "run", lambda **kwargs: seen.update(kwargs)
    )
    monkeypatch.delenv("EWOK_PORT", raising=False)
    ewok_app.main([])
    assert seen["host"] == "127.0.0.1"
    assert seen["port"] == 5055
    assert seen["debug"] is False


def test_entry_point_port_option(monkeypatch):
    import app as ewok_app

    seen = {}
    monkeypatch.setattr(
        ewok_app.app, "run", lambda **kwargs: seen.update(kwargs)
    )
    ewok_app.main(["--port", "6001"])
    assert seen["port"] == 6001
    assert seen["host"] == "127.0.0.1"


def test_wallrender_is_importable_from_the_app():
    import wallrender

    assert wallrender.SCHEMA_VERSION == 1


def test_pillow_is_pinned_to_jawas_range():
    """Text pixels differ between Pillow releases, so EWOK must render with
    the Pillow JAWA's Brander uses (JAWA requirements.txt: >=11.3,<12)."""
    import PIL

    major, minor = (int(p) for p in PIL.__version__.split(".")[:2])
    assert (11, 3) <= (major, minor) < (12, 0)
