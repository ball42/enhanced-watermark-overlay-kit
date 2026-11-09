"""Template designer in a browser: an export that cannot reach EWOK says so."""

import pytest


@pytest.mark.parametrize("button, route", [
    ("#downloadPackage", "**/api/template/package"),
    ("#downloadBundle", "**/api/template/export"),
])
def test_export_says_when_ewok_cannot_be_reached(page, button, route):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.route(route, lambda r: r.abort())
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    if button == "#downloadBundle":
        page.click("#moreActions > summary")
    page.click(button)
    page.wait_for_function("document.querySelector('#ioStatus').textContent.startsWith('Not exported')")
    assert page.text_content("#ioStatus") == "Not exported: could not reach EWOK. Is it still running?"
    assert errors == []
