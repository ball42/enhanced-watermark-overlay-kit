"""Another site can't embed EWOK's files or probe which ids exist: every
response is same-origin only, and a cross-site GET under /api/ is refused."""

import io
import os

import pytest

from tests.test_asset_thumbs import photo_bytes


@pytest.fixture
def logo(client):
    resp = client.post("/api/template/assets", content_type="multipart/form-data",
                       data={"file": (io.BytesIO(photo_bytes()), "logo.jpg")})
    assert resp.status_code == 201
    return "logo"


PATHS = ["/api/template/assets", "/api/template/assets/logo", "/api/template/assets/logo/thumb",
         "/api/template/assets/missing"]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("site", ["cross-site", "same-site"])
def test_cross_site_gets_under_api_are_refused(client, logo, path, site):
    resp = client.get(path, headers={"Sec-Fetch-Site": site, "Sec-Fetch-Dest": "image"})
    assert resp.status_code == 403
    assert resp.is_json and "error" in resp.get_json()
    assert resp.headers["Cross-Origin-Resource-Policy"] == "same-origin"


def test_a_refused_thumb_writes_nothing(client, logo):
    import config
    client.get("/api/template/assets/logo/thumb", headers={"Sec-Fetch-Site": "cross-site"})
    thumbs = os.path.join(config.TEMPLATE_ASSETS_FOLDER, ".thumbs")
    assert not os.path.isdir(thumbs) or os.listdir(thumbs) == []


@pytest.mark.parametrize("path", PATHS[:3])
@pytest.mark.parametrize("site", [None, "same-origin", "none"])
def test_own_and_direct_gets_still_work(client, logo, path, site):
    headers = {"Sec-Fetch-Site": site} if site else {}
    resp = client.get(path, headers=headers)
    assert resp.status_code == 200
    assert resp.headers["Cross-Origin-Resource-Policy"] == "same-origin"


@pytest.mark.parametrize("path", ["/", "/template", "/static/css/style.css"])
def test_every_response_is_same_origin_only(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    assert resp.headers["Cross-Origin-Resource-Policy"] == "same-origin"


def test_pages_open_from_another_site_by_link(client):
    # A top-level navigation from a link elsewhere still opens the designer.
    assert client.get("/template", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 200
