"""Photo-mode fixes (EWOK-08): positions, rotation, fallback font,
gradients, and failures reported instead of swallowed."""

import io
import time

import pytest
from PIL import Image

from tests.conftest import make_test_image
from utils import image_processing as ip


@pytest.mark.parametrize(
    "value, expected",
    [(25, 25), (25.7, 25), ("25", 25), ("25px", 25), ("25%", 50), (" 10 PX ", 10),
     ("50.5%", 101), ("nope", 100), (None, 100), (True, 100)],
)
def test_parse_position(value, expected):
    assert ip.parse_position(value, 200, default=100) == expected


def test_image_overlay_at_px_position_is_drawn(tmp_path):
    logo = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    logo.save(tmp_path / "logo.png")
    base = Image.new("RGBA", (100, 100), (0, 0, 0, 255))
    warnings = []
    out = ip.add_image_overlays(base, [{"filename": "logo.png", "x": "20px", "y": "30.0"}],
                                str(tmp_path), warnings=warnings)
    assert out.getpixel((25, 35))[:3] == (255, 0, 0)
    assert warnings == []


def test_missing_overlay_file_is_reported(tmp_path):
    warnings = []
    ip.add_image_overlays(Image.new("RGBA", (50, 50)), [{"filename": "gone.png"}],
                          str(tmp_path), warnings=warnings)
    assert any("gone.png" in w for w in warnings)


def test_fallback_font_honours_the_size(monkeypatch):
    real = ip.ImageFont.truetype

    def no_system_fonts(font=None, *a, **k):
        if isinstance(font, str):  # a font file path: pretend none exist
            raise OSError("no fonts here")
        return real(font, *a, **k)  # Pillow's built-in font, from bytes

    monkeypatch.setattr(ip.ImageFont, "truetype", no_system_fonts)
    small = ip.load_font(10)
    big = ip.load_font(60)
    assert big.getbbox("Hg")[3] > small.getbbox("Hg")[3] * 3


@pytest.mark.parametrize("direction", ["vertical", "horizontal", "diagonal"])
def test_gradient_is_fast_and_runs_start_to_end(direction):
    img = Image.new("RGBA", (1200, 900))
    started = time.monotonic()
    out = ip.add_background(img, {"type": "gradient", "start_color": "#000000",
                                  "end_color": "#FFFFFF", "direction": direction})
    assert time.monotonic() - started < 1.0
    rgb = out.convert("RGB")
    assert rgb.getpixel((0, 0))[0] < 20
    assert rgb.getpixel((1199, 899))[0] > 235


def test_rotation_is_smooth(client):
    """Bicubic rotation leaves intermediate edge colours; nearest-neighbour
    only ever has the two original colours."""
    img = Image.new("RGBA", (120, 120), (0, 0, 0, 255))
    for x in range(40, 80):
        for y in range(40, 80):
            img.putpixel((x, y), (255, 255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    name = client.post("/api/upload", data={"file": (buf, "sq.png")},
                       content_type="multipart/form-data").get_json()["filename"]
    resp = client.post("/api/process", json={"filename": name, "rotation": 30})
    out_name = resp.get_json()["processed_filename"]
    out = Image.open(io.BytesIO(client.get(f"/api/preview/{out_name}").data)).convert("L")
    levels = {v for v in out.getdata() if 10 < v < 245}
    assert len(levels) > 10


def test_process_reports_overlay_problems(client):
    buf = make_test_image(80, 80)
    name = client.post("/api/upload", data={"file": (buf, "a.png")},
                       content_type="multipart/form-data").get_json()["filename"]
    resp = client.post("/api/process", json={
        "filename": name, "image_overlays": [{"filename": "missing.png", "x": 1, "y": 1}]})
    body = resp.get_json()
    assert resp.status_code == 200
    assert any("missing.png" in w for w in body["warnings"])
