"""The trash keeps every copy of an id from the last day, not only the latest:
replacing or deleting the same asset twice in a day loses neither copy."""

import os
import time

import config
from tests.test_template_api import upload

DAY = 24 * 3600


def served(client, asset_id="logo"):
    return client.get(f"/api/template/assets/{asset_id}").data


def trash_files():
    found = []
    for root, _dirs, files in os.walk(os.path.join(config.TEMPLATE_ASSETS_FOLDER, ".trash")):
        found += [os.path.join(root, name) for name in files]
    return sorted(found)


def restore(client, asset_id="logo", source=None):
    query = f"?from={source}" if source else ""
    return client.post(f"/api/template/assets/{asset_id}/restore{query}")


def test_replacing_twice_in_a_day_can_bring_back_both_older_copies(client):
    upload(client, "logo.png", size=(10, 10))
    a = served(client)
    upload(client, "logo.png", size=(20, 20))
    b = served(client)
    upload(client, "logo.png", size=(30, 30))
    assert len(trash_files()) == 2  # a and b both wait in the trash

    # Newest first: the copy C pushed out (B), then the one B pushed out (A).
    client.delete("/api/template/assets/logo")
    assert restore(client).status_code == 200
    assert served(client) == b
    client.delete("/api/template/assets/logo")
    assert restore(client).status_code == 200
    assert served(client) == a


def test_deleting_the_same_id_twice_in_a_day_keeps_both_copies(client):
    upload(client, "logo.png", size=(10, 10))
    a = served(client)
    client.delete("/api/template/assets/logo")
    upload(client, "logo.png", size=(20, 20))
    b = served(client)
    client.delete("/api/template/assets/logo")
    assert len(trash_files()) == 2

    assert restore(client, source="deleted").status_code == 200
    assert served(client) == b
    # B is back in the library; A is still in the trash, not lost.
    os.remove(os.path.join(config.TEMPLATE_ASSETS_FOLDER, "logo.png"))
    assert restore(client, source="deleted").status_code == 200
    assert served(client) == a
    assert restore(client, source="deleted").status_code == 404


def test_every_kept_copy_still_leaves_after_a_day(client):
    upload(client, "logo.png", size=(10, 10))
    upload(client, "logo.png", size=(20, 20))
    upload(client, "logo.png", size=(30, 30))
    client.delete("/api/template/assets/logo")
    assert len(trash_files()) == 3
    stale = time.time() - DAY - 60
    for path in trash_files():
        os.utime(path, (stale, stale))
    client.get("/api/template/assets")  # any library request empties the trash
    assert trash_files() == []
    assert restore(client).status_code == 404


def test_a_copy_trashed_before_this_change_still_restores(client):
    # Earlier versions kept one copy per id as <id>.<ext> in each slot.
    upload(client, "logo.png", size=(10, 10))
    a = served(client)
    path = os.path.join(config.TEMPLATE_ASSETS_FOLDER, "logo.png")
    os.makedirs(os.path.join(config.TEMPLATE_ASSETS_FOLDER, ".trash"), exist_ok=True)
    os.replace(path, os.path.join(config.TEMPLATE_ASSETS_FOLDER, ".trash", "logo.png"))
    upload(client, "logo.png", size=(20, 20))
    client.delete("/api/template/assets/logo")
    # The newer delete comes back first, then the old-style copy.
    assert restore(client, source="deleted").status_code == 200
    assert served(client) != a
    os.remove(os.path.join(config.TEMPLATE_ASSETS_FOLDER, "logo.png"))
    assert restore(client, source="deleted").status_code == 200
    assert served(client) == a


def test_the_trash_stays_out_of_the_library(client):
    upload(client, "logo.png", size=(10, 10))
    upload(client, "logo.png", size=(20, 20))
    client.delete("/api/template/assets/logo")
    assert client.get("/api/template/assets").get_json()["assets"] == []
