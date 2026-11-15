"""Photo editor wallpaper sizes match the template designer's canvases and devices."""

import html as htmllib
import re

from config import TEMPLATE_CANVASES, WALLPAPER_PRESET_GROUPS, WALLPAPER_PRESETS
from wallrender.devices import device_profiles


def size_options(client):
    html = client.get("/").get_data(as_text=True)
    select = html[html.index('id="wallpaperPreset"'):]
    select = select[:select.index("</select>")]
    groups = re.findall(r'<optgroup label="([^"]+)">', select)
    options = [re.sub(r"\s+", " ", htmllib.unescape(o)).strip()
               for o in re.findall(r"<option [^>]*>([^<]+)</option>", select)]
    return groups, options


def test_the_list_starts_with_the_iphone_template_canvas(client):
    groups, options = size_options(client)
    assert options[0] == "Template canvas: iPhone (portrait) 1290×2796"
    assert groups == ["Template canvases", "Devices", "Mac and displays", "Other sizes"]


def test_every_template_canvas_is_in_the_photo_editor_list(client):
    _, options = size_options(client)
    for name, (w, h) in TEMPLATE_CANVASES.items():
        assert f"Template canvas: {name} {w}×{h}" in options
    # The canvases come first, in the designer's order.
    assert options[:len(TEMPLATE_CANVASES)] == [
        f"Template canvas: {name} {w}×{h}" for name, (w, h) in TEMPLATE_CANVASES.items()]


def test_every_device_profile_follows_by_name_then_the_mac_sizes(client):
    _, options = size_options(client)
    devices = [f"{p['name']} {p['screen'][0]}×{p['screen'][1]}" for p in device_profiles()]
    start = len(TEMPLATE_CANVASES)
    assert options[start:start + len(devices)] == devices
    assert options.index('MacBook Air 13" 2560×1600') > start + len(devices) - 1
    assert "Pro Display XDR 6016×3384" in options
    assert options[-1] == "Optimized"
    assert not any(o.startswith("iPhone 15") for o in options)


def test_the_photo_api_knows_every_listed_size(client):
    listed = [name for _, group in WALLPAPER_PRESET_GROUPS for name in group]
    assert listed == list(WALLPAPER_PRESETS)
    assert WALLPAPER_PRESETS["Template canvas: iPad (square, both orientations)"] == (2732, 2732)
