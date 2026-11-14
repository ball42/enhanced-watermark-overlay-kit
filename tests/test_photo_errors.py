"""Photo editor API errors are one plain sentence, never Python's text."""

import json
import logging

import pytest

from tests.conftest import make_test_image

UNEXPECTED = "EWOK hit an error; the log has details."


def upload(client):
    resp = client.post("/api/upload", data={"file": (make_test_image(), "photo.png")},
                       content_type="multipart/form-data")
    return resp.get_json()["filename"]


def process(client, **data):
    return client.post("/api/process", data=json.dumps(data), content_type="application/json")


@pytest.mark.parametrize("field, label", [
    ("opacity", "Image Opacity"), ("saturation", "Color Saturation"), ("brightness", "Brightness"),
    ("contrast", "Contrast"), ("blur_sharpen", "Blur / Sharpen"), ("rotation", "Rotation"),
    ("resize", "Custom Resize"),
])
@pytest.mark.parametrize("bad", ["50", None, True, [1]])
def test_a_setting_that_is_not_a_number_is_named(client, field, label, bad):
    resp = process(client, filename=upload(client), **{field: bad})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == f"{label} must be a number."


def test_the_reported_opacity_string_is_a_bad_setting_not_a_500(client):
    # The case from the ticket: Python's TypeError text used to come back.
    resp = process(client, filename=upload(client), opacity="50")
    assert resp.status_code == 400
    assert "unsupported operand" not in resp.get_data(as_text=True)


def test_an_unexpected_error_returns_a_fixed_message_and_logs_the_exception(client, caplog,
                                                                           monkeypatch):
    def boom(*args, **kwargs):
        raise TypeError("unsupported operand type(s) for /: 'str' and 'float'")

    monkeypatch.setattr("views.api.add_watermark", boom)
    filename = upload(client)
    with caplog.at_level(logging.ERROR, logger="views.api"):
        resp = process(client, filename=filename, watermark={"enabled": True})
    assert resp.status_code == 500
    assert resp.get_json() == {"error": UNEXPECTED}
    records = [r for r in caplog.records if r.name == "views.api" and r.levelno == logging.ERROR]
    assert len(records) == 1 and records[0].exc_info is not None


def test_a_body_that_is_not_json_is_refused_plainly(client):
    resp = client.post("/api/process", data="{nope", content_type="application/json")
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "No filename provided"}
