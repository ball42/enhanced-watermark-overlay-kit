"""Deleting a library asset can be undone: the file waits in a trash folder for a day."""

import os
import time

import config
from tests.test_template_api import export, logo_template, upload

DAY = 24 * 3600


def trash():
    return os.path.join(config.TEMPLATE_ASSETS_FOLDER, ".trash")


def trashed_ids():
    """Ids in the deleted slot; each copy is kept as <id>.<stamp>.<ext>."""
    names = [n for n in os.listdir(trash()) if os.path.isfile(os.path.join(trash(), n))]
    return sorted(n.split(".")[0] for n in names)


def ids(client):
    return [a["id"] for a in client.get("/api/template/assets").get_json()["assets"]]


def test_delete_then_undo_restores_the_file_and_the_library_entry(client):
    upload(client, "logo.png")
    assert client.delete("/api/template/assets/logo").status_code == 204
    assert ids(client) == []
    assert export(client, logo_template()).status_code == 422

    resp = client.post("/api/template/assets/logo/restore")
    assert resp.status_code == 200
    assert resp.get_json() == {"id": "logo", "width": 40, "height": 30}
    assert ids(client) == ["logo"]
    assert client.get("/api/template/assets/logo").status_code == 200
    # A template that uses it opens and exports again.
    assert export(client, logo_template()).status_code == 200


def test_the_trash_is_not_part_of_the_library(client):
    upload(client, "logo.png")
    upload(client, "spare.png")
    client.delete("/api/template/assets/logo")
    assert ids(client) == ["spare"]
    assert trashed_ids() == ["logo"]


def test_undo_twice_says_there_is_nothing_to_undo(client):
    upload(client, "logo.png")
    client.delete("/api/template/assets/logo")
    assert client.post("/api/template/assets/logo/restore").status_code == 200
    resp = client.post("/api/template/assets/logo/restore")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "Nothing to undo: logo is no longer in the trash."


def test_undo_never_overwrites_an_asset_uploaded_since(client):
    upload(client, "logo.png", size=(40, 30))
    client.delete("/api/template/assets/logo")
    upload(client, "logo.png", size=(10, 10))
    resp = client.post("/api/template/assets/logo/restore")
    assert resp.status_code == 409
    assert resp.get_json()["error"] == "Not restored: a newer logo is in the library."
    assert client.get("/api/template/assets").get_json()["assets"] == [
        {"id": "logo", "width": 10, "height": 10}]


def test_a_jpeg_comes_back_as_a_jpeg(client):
    upload(client, "photo.jpg", fmt="JPEG")
    client.delete("/api/template/assets/photo")
    assert client.post("/api/template/assets/photo/restore").status_code == 200
    assert os.path.isfile(os.path.join(config.TEMPLATE_ASSETS_FOLDER, "photo.jpg"))


def test_the_trash_is_emptied_after_a_day(client):
    upload(client, "old.png")
    upload(client, "new.png")
    client.delete("/api/template/assets/old")
    stale = time.time() - DAY - 60
    (old,) = os.listdir(trash())
    os.utime(os.path.join(trash(), old), (stale, stale))
    client.delete("/api/template/assets/new")  # any delete empties what is over a day old
    assert trashed_ids() == ["new"]
    resp = client.post("/api/template/assets/old/restore")
    assert resp.status_code == 404


def test_the_day_counts_from_the_delete_not_the_upload(client):
    upload(client, "logo.png")
    path = os.path.join(config.TEMPLATE_ASSETS_FOLDER, "logo.png")
    stale = time.time() - 3 * DAY
    os.utime(path, (stale, stale))
    client.delete("/api/template/assets/logo")
    client.get("/api/template/assets")
    assert client.post("/api/template/assets/logo/restore").status_code == 200


def test_restore_refuses_an_id_outside_the_pattern(client):
    resp = client.post("/api/template/assets/Bad.Id/restore")
    assert resp.status_code == 404
    assert resp.get_json()["error"].startswith("Nothing to undo")
