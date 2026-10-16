"""Template designer in a browser: starting over and keeping a draft."""

import pytest


def layer_count(page):
    return page.locator("#layerList > li").count()


@pytest.fixture()
def designer(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    return page


def add_text_layer(page):
    before = layer_count(page)
    page.click('[data-add="text"]')
    page.wait_for_function(f"document.querySelectorAll('#layerList > li').length > {before}")


def test_new_template_starts_over_after_a_confirm(designer):
    page = designer
    add_text_layer(page)
    page.fill("#tplName", "Lobby")
    assert layer_count(page) == 3

    page.once("dialog", lambda d: d.dismiss())
    page.click("#newTemplate")
    assert layer_count(page) == 3
    assert page.input_value("#tplName") == "Lobby"

    messages = []
    page.once("dialog", lambda d: (messages.append(d.message), d.accept()))
    page.click("#newTemplate")
    assert "Start a new template?" in messages[0]
    assert layer_count(page) == 2
    assert page.input_value("#tplName") == "Untitled template"
    assert page.inner_text("#ioStatus") == "Started a new template."


def leave_prompts(page):
    """Close the tab the way a user does and report whether it asked first."""
    asked = []

    def on_dialog(dialog):
        asked.append(dialog.type)
        dialog.dismiss()  # stay on the page

    page.on("dialog", on_dialog)
    other = page.context.new_page()  # keeps the event loop going if the tab closes
    page.close(run_before_unload=True)
    other.wait_for_timeout(500)
    return "beforeunload" in asked


def test_a_reload_restores_the_draft(designer):
    page = designer
    add_text_layer(page)
    page.fill("#tplName", "Lobby")
    page.wait_for_timeout(500)  # past the preview debounce, which saves the draft
    page.reload()
    page.wait_for_function("document.querySelectorAll('#layerList > li').length === 3")
    assert page.input_value("#tplName") == "Lobby"
    assert page.inner_text("#ioStatus") == "Restored your last draft."


def test_new_template_is_what_the_next_reload_keeps(designer):
    page = designer
    add_text_layer(page)
    page.wait_for_timeout(500)
    page.once("dialog", lambda d: d.accept())
    page.click("#newTemplate")
    page.wait_for_timeout(500)
    page.reload()
    page.wait_for_selector("#previewImage:not([hidden])")
    assert layer_count(page) == 2
    assert page.input_value("#tplName") == "Untitled template"


def test_leaving_with_an_edit_not_downloaded_asks_first(designer):
    page = designer
    add_text_layer(page)
    assert leave_prompts(page)


def test_leaving_after_a_download_does_not_ask(designer):
    page = designer
    add_text_layer(page)
    page.wait_for_timeout(500)
    with page.expect_download():
        page.click("#downloadPackage")
    page.wait_for_function("document.querySelector('#ioStatus').textContent.startsWith('Downloaded')")
    assert not leave_prompts(page)


def test_a_fresh_page_does_not_ask(designer):
    assert not leave_prompts(designer)
