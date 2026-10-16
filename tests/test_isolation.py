"""Each test's app writes to that test's own folders.

views.api is imported here at module level on purpose: the routes must read
the folders when a request runs, not when the module is first imported.
"""

import os

from tests.conftest import make_test_image
from views import api  # noqa: F401  (import order must not matter)


def _upload_and_process(client):
    resp = client.post("/api/upload", data={"file": (make_test_image(), "p.png")},
                       content_type="multipart/form-data")
    assert resp.status_code == 200
    filename = resp.get_json()["filename"]
    resp = client.post("/api/process", json={"filename": filename})
    assert resp.status_code == 200
    return filename, resp.get_json()["processed_filename"]


def test_first_upload_lands_in_this_tests_folders(client, tmp_path):
    filename, processed = _upload_and_process(client)
    assert os.path.exists(tmp_path / "uploads" / filename)
    assert os.path.exists(tmp_path / "temp" / processed)


def test_second_upload_lands_in_this_tests_folders(client, tmp_path):
    filename, processed = _upload_and_process(client)
    assert os.path.exists(tmp_path / "uploads" / filename)
    assert os.path.exists(tmp_path / "temp" / processed)


def test_cleanup_hook_cleans_the_folders_the_routes_use(client, tmp_path, monkeypatch):
    from utils import cleanup
    filename, processed = _upload_and_process(client)
    old = [tmp_path / "uploads" / filename, tmp_path / "temp" / processed]
    for path in old:
        os.utime(path, (1, 1))
    monkeypatch.setattr(cleanup, "_last_cleanup", 0)
    client.get("/")
    assert not any(os.path.exists(path) for path in old)
