"""Template designer in a browser: the stress view renders each role variant."""


def test_stress_shows_one_figure_per_role(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.check("#rolesOn")
    page.click("#addVariant")
    page.click("#addVariant")
    page.check("#stressToggle")
    page.wait_for_function("document.querySelectorAll('#stressRenders figure').length === 4")
    captions = page.locator("#stressRenders figcaption").all_inner_texts()
    assert captions == ["Every value long", "Every value empty", "Role: Role 1", "Role: Role 2"]
