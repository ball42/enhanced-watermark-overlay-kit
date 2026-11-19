"""Static files: the pages name each with a hash of its bytes, and a hashed
URL is cached, so a reload does not revalidate every file."""

import re

import pytest

import app_factory


def static_urls(client, path):
    body = client.get(path).get_data(as_text=True)
    return re.findall(r"""(?:src|href)="(/static/[^"#]+)""", body)


@pytest.mark.parametrize("path", ["/", "/template"])
def test_every_static_file_a_page_names_carries_its_hash(client, path):
    urls = static_urls(client, path)
    assert len(urls) >= 10
    for url in urls:
        assert re.search(r"\?v=[0-9a-f]{12}$", url), url


@pytest.mark.parametrize("path", ["/", "/template"])
def test_a_hashed_static_file_is_cached_for_at_least_an_hour(client, path):
    for url in static_urls(client, path):
        resp = client.get(url)
        assert resp.status_code == 200, url
        cc = resp.cache_control
        assert not cc.no_cache and cc.max_age >= 3600, (url, resp.headers.get("Cache-Control"))
        resp.close()
    assert app_factory.STATIC_MAX_AGE >= 3600


def test_an_unhashed_static_file_still_revalidates(client):
    resp = client.get("/static/js/template.js")
    assert resp.cache_control.no_cache
    resp.close()


def test_a_changed_file_gets_a_new_url(app, client, tmp_path, monkeypatch):
    target = tmp_path / "probe.css"
    target.write_text("a{}")
    monkeypatch.setattr(app, "static_folder", str(tmp_path))
    static_v = app.jinja_env.globals["static_v"]
    first = static_v("probe.css")
    target.write_text("a{color:blue}")
    assert static_v("probe.css") != first


def test_the_icon_font_url_carries_its_hash(client):
    css = client.get("/static/vendor/fontawesome/css/icons.min.css").get_data(as_text=True)
    assert re.search(r"fa-solid-900\.woff2\?v=[0-9a-f]{12}\)", css)
