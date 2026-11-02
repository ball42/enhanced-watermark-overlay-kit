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


def test_help_explains_the_options(capsys):
    import app as ewok_app

    with pytest.raises(SystemExit):
        ewok_app.main(["--help"])
    out = capsys.readouterr().out
    assert "Run EWOK, the local watermark editor and Brander template designer." in out
    assert "Port to serve on (default 5055, or EWOK_PORT)." in out
    assert "--open" in out
    assert "SECRET_KEY" not in out


def test_starting_without_secret_key_prints_no_warning(tmp_path):
    import subprocess
    import sys

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
    done = subprocess.run([sys.executable, "app.py", "--help"], cwd=root, env=env,
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0
    assert "SECRET_KEY" not in done.stdout + done.stderr


def test_open_flag_opens_the_designer(monkeypatch):
    import app as ewok_app

    timers = []

    class FakeTimer:
        def __init__(self, delay, func, args=()):
            timers.append((delay, func, args))

        def start(self):
            pass

    monkeypatch.setattr(ewok_app.threading, "Timer", FakeTimer)
    monkeypatch.setattr(ewok_app.app, "run", lambda **kwargs: None)
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    ewok_app.main(["--open", "--port", "6002"])
    assert timers == [(1.0, ewok_app.webbrowser.open, ("http://127.0.0.1:6002/template",))]

    timers.clear()
    ewok_app.main(["--port", "6002"])
    assert timers == []
