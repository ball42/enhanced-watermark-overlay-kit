"""Template designer in a browser: a low-contrast warning under a role
render carries the same fixes as the sample's, worked out against that
role's own background."""

from tests.browser.test_template_ready_for_jawa import set_color

ROLE = "#stressRenders figure:has(figcaption:text-is('Role: Role 1'))"


def white_role(page):
    """The default template's white text, with Role 1 on a white background."""
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    page.click("#rolesSection > summary")  # the Roles section starts collapsed
    page.check("#rolesOn")
    page.click("#addVariant")
    card = page.locator("#variantList > li").first
    card.locator("select").first.select_option("color")
    set_color(page, "#ffffff", "#variantList input[aria-label='Role: Role 1 background color']")
    page.click("#tabStress")
    page.check("#stressToggle")
    page.wait_for_selector(f"{ROLE} li:has-text('low contrast')")
    return page.locator(ROLE)


def test_a_role_render_offers_dark_text_and_it_fixes_that_role(page):
    role = white_role(page)
    item = role.locator("li", has_text="low contrast")
    assert item.locator("button", has_text="Add a backdrop").count() == 1
    item.locator("button", has_text="Use dark text").click()
    say = page.text_content("#stressSay")
    assert say.startswith("✓ Contrast 1.") and "(on Role: Role 1)" in say
    page.wait_for_selector(f"{ROLE} li:has-text('low contrast')", state="detached")
    # The navy sample render now has the dark text: its own warning says so.
    page.wait_for_function("document.querySelector('#warningList').textContent.includes('low contrast')")
    page.click("#stressSay button:has-text('Undo')")
    assert page.text_content("#stressSay").startswith("Undone")


def test_a_role_backdrop_is_worked_out_against_the_role_background(page):
    role = white_role(page)
    sent = []
    page.on("request", lambda r: sent.append(r) if r.url.endswith("/api/template/backdrop") else None)
    role.locator("button", has_text="Add a backdrop").click()
    page.wait_for_function("document.querySelector('#stressSay').textContent.includes('Contrast')")
    assert sent[-1].post_data_json["values"]["role"] == "role1"
    say = page.text_content("#stressSay")
    assert "Added a dark backdrop" in say and "(on Role: Role 1)" in say
    page.wait_for_selector(f"{ROLE} li:has-text('low contrast')", state="detached")


def test_stress_renders_fit_a_phone_with_a_long_role_value(page):
    """The long render's role value is one unbroken "WWWW…": its warning
    wraps instead of widening the page."""
    page.set_viewport_size({"width": 390, "height": 900})
    white_role(page)
    assert page.evaluate("document.documentElement.scrollWidth") == 390
