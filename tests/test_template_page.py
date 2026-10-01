"""Template mode T2: the editor page and its navigation."""


def test_template_page_renders(client):
    resp = client.get("/template")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'id="templateEditor"' in body
    assert "/static/js/template.js" in body
    # Brander's variables are offered for insertion.
    for name in ("device_name", "serial_number", "asset_tag", "jss_id", "location.building"):
        assert f'value="{name}"' in body
    # Canvas presets, including the square iPad canvas that survives rotation.
    assert "2732" in body and "1290" in body


def test_photo_and_template_pages_link_to_each_other(client):
    assert 'href="/template"' in client.get("/").get_data(as_text=True)
    assert 'href="/"' in client.get("/template").get_data(as_text=True)


def test_editor_script_and_styles_are_served(client):
    assert client.get("/static/js/template.js").status_code == 200
    assert client.get("/static/css/template.css").status_code == 200
