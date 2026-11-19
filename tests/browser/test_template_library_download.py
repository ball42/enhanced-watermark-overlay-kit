"""The Assets panel offers the whole library as a .zip once it has an asset,
and the preflight names the Pillow JAWA renders with."""

import io
import zipfile

from tests.test_template_api import image_bytes


def test_download_library_appears_with_an_asset_and_downloads_a_zip(page, tmp_path):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.click("#assetsSection summary")
    assert page.is_hidden("#downloadLibrary")
    logo = tmp_path / "logo.png"
    logo.write_bytes(image_bytes((40, 30), "PNG").getvalue())
    page.set_input_files("#assetFile", str(logo))
    page.wait_for_selector("#downloadLibrary:not([hidden])")
    with page.expect_download() as info:
        page.click("#downloadLibrary")
    assert info.value.suggested_filename.startswith("ewok-asset-library-")
    with zipfile.ZipFile(io.BytesIO(open(info.value.path(), "rb").read())) as library:
        assert library.namelist() == ["logo.png"]


def test_the_preflight_warns_when_pillow_differs_from_jawa(page, monkeypatch):
    import config
    monkeypatch.setattr(config, "PILLOW_TARGET", "11.3")
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.click("#preflightToggle")
    line = page.locator(".tpl-preflight-line", has_text="Pillow")
    assert line.text_content().startswith("Preview may differ from devices: EWOK runs Pillow 13.0, JAWA 11.3.")
    assert "is-warn" in line.get_attribute("class")
