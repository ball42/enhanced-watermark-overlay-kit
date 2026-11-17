"""Template designer in a browser: the asset library loads thumbnails, not originals."""

from tests.test_asset_thumbs import photo_bytes


def test_the_library_loads_small_thumbnails_and_never_the_originals(page):
    original = photo_bytes()
    for k in range(1, 4):
        resp = page.request.post("/api/template/assets", multipart={
            "file": {"name": f"photo-{k}.jpg", "mimeType": "image/jpeg", "buffer": original}})
        assert resp.status == 201
    fetched = {}
    page.on("requestfinished", lambda req: fetched.__setitem__(req.url, req.sizes()["responseBodySize"]))
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.wait_for_function("[...document.querySelectorAll('#assetList img')].length === 3"
                           " && [...document.querySelectorAll('#assetList img')].every(i => i.complete && i.naturalWidth)")
    sizes = page.eval_on_selector_all("#assetList img", "imgs => imgs.map(i => [i.naturalWidth, i.naturalHeight])")
    assert sizes == [[44, 96]] * 3
    page.wait_for_load_state("networkidle")
    assets = {url: size for url, size in fetched.items() if "/api/template/assets/" in url}
    assert sorted(url.rsplit("/assets/", 1)[1] for url in assets) == [f"photo-{k}/thumb" for k in range(1, 4)]
    assert sum(assets.values()) < 3 * 12_000 < len(original)
