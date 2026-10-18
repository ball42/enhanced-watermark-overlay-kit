"""Template designer in a browser: a text layer's weight."""

import base64
import io
import json

from PIL import Image


def ink(data_url):
    img = Image.open(io.BytesIO(base64.b64decode(data_url.split(",", 1)[1]))).convert("L")
    return sum(1 for v in img.getdata() if v > 127)


def draft_layer(page, i):
    return json.loads(page.evaluate("localStorage.getItem('ewok-template-draft')"))["layers"][i]


def test_choosing_bold_makes_the_preview_text_bold(page):
    page.goto("/template")
    page.wait_for_selector("#previewImage:not([hidden])")
    assert page.input_value("#propWeight") == "regular"
    regular = page.get_attribute("#previewImage", "src")

    page.select_option("#propWeight", "bold")
    page.wait_for_function("s => document.querySelector('#previewImage').src !== s", arg=regular)
    bold = page.get_attribute("#previewImage", "src")
    assert draft_layer(page, 0)["weight"] == "bold"
    assert ink(bold) > ink(regular)

    # Back to Regular leaves no weight in the template, as older wallrender expects.
    page.select_option("#propWeight", "regular")
    page.wait_for_function("s => document.querySelector('#previewImage').src !== s", arg=bold)
    assert "weight" not in draft_layer(page, 0)
