"""EWOK says when its Pillow differs from the one JAWA renders with."""

import PIL

import config
from app import pillow_line_on_start
from tests.test_template_api import TEMPLATE


def preview(client):
    return client.post("/api/template/preview", json={"template": TEMPLATE, "values": {}}).get_json()


def test_the_default_target_is_the_pillow_jawa_pins():
    assert config.PILLOW_TARGET_DEFAULT == "13.0"


def test_a_different_pillow_warns_in_the_preview(client, monkeypatch):
    monkeypatch.setattr(PIL, "__version__", "11.3.0")
    monkeypatch.setattr(config, "PILLOW_TARGET", "13.0")
    pillow = preview(client)["target"]["pillow"]
    assert pillow == {"ewok": "11.3", "jawa": "13.0", "matches": False,
                      "warning": "Preview may differ from devices: EWOK runs Pillow 11.3, JAWA 13.0."}


def test_the_same_major_and_minor_does_not_warn(client, monkeypatch):
    monkeypatch.setattr(PIL, "__version__", "13.0.2")
    monkeypatch.setattr(config, "PILLOW_TARGET", "13.0")
    assert preview(client)["target"]["pillow"] == {"ewok": "13.0", "jawa": "13.0", "matches": True}


def test_the_ewok_command_prints_one_line_only_on_a_mismatch(monkeypatch, capsys):
    monkeypatch.setattr(config, "PILLOW_TARGET", "13.0")
    monkeypatch.setattr(PIL, "__version__", "11.3.0")
    pillow_line_on_start()
    assert capsys.readouterr().out == \
        "Warning: Preview may differ from devices: EWOK runs Pillow 11.3, JAWA 13.0.\n"
    monkeypatch.setattr(PIL, "__version__", "13.0.0")
    pillow_line_on_start()
    assert capsys.readouterr().out == ""
