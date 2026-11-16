"""Opening a template whose asset id is already in the library never loses
the library's copy: EWOK asks first, and a replaced copy goes to the trash."""

import base64
import io
import json
import os

import config
from tests.test_template_api import image_bytes, logo_template, upload



def package(size):
    data = image_bytes(size, "PNG").getvalue()
    return json.dumps({"kind": "brander-template", "format": 1, "name": "Ward iPads",
                       "template": logo_template(),
                       "assets": {"logo": base64.b64encode(data).decode()}}).encode(), data


def open_package(client, data, replace=None):
    form = {"file": (io.BytesIO(data), "ward-ipads.brander.json")}
    if replace is not None:
        form["replace"] = replace
    return client.post("/api/template/import", data=form, content_type="multipart/form-data")


def served(client):
    return client.get("/api/template/assets/logo").data


def trashed():
    folder = os.path.join(config.TEMPLATE_ASSETS_FOLDER, ".trash")
    return sorted(os.listdir(folder)) if os.path.isdir(folder) else []


def test_opening_asks_before_replacing_and_changes_nothing(client):
    upload(client, "logo.png")
    mine = served(client)
    data, _ = package((12, 12))
    resp = open_package(client, data)
    assert resp.status_code == 409
    assert resp.get_json()["conflicts"] == ["logo"]
    assert served(client) == mine
    assert trashed() == []


def test_declining_keeps_the_library_copy_byte_for_byte(client):
    upload(client, "logo.png")
    mine = served(client)
    data, _ = package((12, 12))
    body = open_package(client, data, replace="no").get_json()
    assert body["template"] == logo_template()
    assert body["kept"] == ["logo"] and body["replaced"] == []
    assert served(client) == mine


def test_replacing_keeps_the_old_copy_in_the_trash_and_restore_brings_it_back(client):
    upload(client, "logo.png")
    mine = served(client)
    data, theirs = package((12, 12))
    body = open_package(client, data, replace="yes").get_json()
    assert body["replaced"] == ["logo"]
    assert served(client) == theirs
    assert len(trashed()) == 1  # the old logo, kept for a day

    # Delete the newer one, then restore: the library's own logo is back.
    assert client.delete("/api/template/assets/logo").status_code == 204
    resp = client.post("/api/template/assets/logo/restore")
    assert resp.status_code == 200
    assert served(client) == mine


def test_undo_delete_still_brings_back_what_was_deleted(client):
    upload(client, "logo.png")
    data, theirs = package((12, 12))
    open_package(client, data, replace="yes")
    client.delete("/api/template/assets/logo")
    resp = client.post("/api/template/assets/logo/restore?from=deleted")
    assert resp.status_code == 200
    assert served(client) == theirs


def test_an_identical_asset_is_not_a_conflict(client):
    upload(client, "logo.png")
    mine = served(client)
    data = json.dumps({"kind": "brander-template", "format": 1, "template": logo_template(),
                       "assets": {"logo": base64.b64encode(mine).decode()}}).encode()
    resp = open_package(client, data)
    assert resp.status_code == 200
    assert resp.get_json()["replaced"] == []
    assert trashed() == []


def test_uploading_over_an_asset_also_keeps_the_old_copy(client):
    upload(client, "logo.png")
    mine = served(client)
    upload(client, "logo.png", size=(20, 20))
    client.delete("/api/template/assets/logo")
    client.post("/api/template/assets/logo/restore")
    assert served(client) == mine
