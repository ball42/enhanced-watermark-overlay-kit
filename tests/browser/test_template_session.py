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
