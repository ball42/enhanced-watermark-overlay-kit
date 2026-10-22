"""Template designer in a browser: the name and export actions stay in reach."""

import pytest

IN_VIEW = """(sel) => {
  const r = document.querySelector(sel).getBoundingClientRect();
  return r.width > 0 && r.top >= 0 && r.bottom <= window.innerHeight;
}"""


@pytest.mark.parametrize("size", [(1280, 800), (390, 844)])
def test_export_actions_stay_visible_while_the_controls_scroll(page, size):
    page.set_viewport_size({"width": size[0], "height": size[1]})
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(100)
    for sel in ("#tplName", "#downloadPackage", ".tpl-file-btn:has(#openTemplate)", "#moreActions > summary"):
        assert page.evaluate(IN_VIEW, sel), f"{sel} scrolled out of view at {size}"


def test_one_solid_primary_and_the_rest_under_more(page):
    page.goto("/template")
    bar = page.locator(".tpl-actionbar")
    solid = bar.locator(".btn:not(.btn-outline)")
    assert solid.count() == 1
    assert solid.first.get_attribute("id") == "downloadPackage"
    assert not page.is_visible("#downloadBundle")
    page.click("#moreActions > summary")
    for sel in ("#newTemplate", "#downloadBundle", "#downloadJson"):
        assert page.is_visible(sel)
    with page.expect_download():
        page.click("#downloadJson")
    assert not page.is_visible("#downloadJson")  # picking an item closes the menu
