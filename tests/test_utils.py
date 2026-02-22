"""Tests for image processing utility functions."""

import pytest
from PIL import Image

from utils.image_processing import hex_to_rgb, load_font, resize_for_wallpaper


# ── hex_to_rgb ─────────────────────────────────


class TestHexToRgb:
    def test_valid_with_hash(self):
        assert hex_to_rgb("#FF0000") == (255, 0, 0)

    def test_valid_without_hash(self):
        assert hex_to_rgb("00FF00") == (0, 255, 0)

    def test_valid_lowercase(self):
        assert hex_to_rgb("#abcdef") == (171, 205, 239)

    def test_valid_mixed_case(self):
        assert hex_to_rgb("#AaBbCc") == (170, 187, 204)

    def test_black(self):
        assert hex_to_rgb("#000000") == (0, 0, 0)

    def test_white(self):
        assert hex_to_rgb("#FFFFFF") == (255, 255, 255)

    def test_invalid_short(self):
        assert hex_to_rgb("#FFF") == (0, 0, 0)

    def test_invalid_chars(self):
        assert hex_to_rgb("#ZZZZZZ") == (0, 0, 0)

    def test_invalid_empty(self):
        assert hex_to_rgb("") == (0, 0, 0)

    def test_invalid_none(self):
        assert hex_to_rgb(None) == (0, 0, 0)

    def test_invalid_number(self):
        assert hex_to_rgb(123) == (0, 0, 0)

    def test_whitespace_stripped(self):
        assert hex_to_rgb("  #FF0000  ") == (255, 0, 0)


# ── load_font ──────────────────────────────────


class TestLoadFont:
    def test_returns_font_object(self):
        font = load_font(24)
        assert font is not None

    def test_different_sizes(self):
        small = load_font(12)
        large = load_font(48)
        assert small is not None
        assert large is not None


# ── resize_for_wallpaper ───────────────────────


class TestResizeForWallpaper:
    def _make_image(self, w=200, h=300):
        return Image.new("RGBA", (w, h), (255, 0, 0, 255))

    def test_stretch_mode(self):
        img = self._make_image(200, 300)
        result = resize_for_wallpaper(img, (1179, 2556), "stretch")
        assert result.size == (1179, 2556)

    def test_crop_mode_wider_image(self):
        img = self._make_image(400, 200)
        result = resize_for_wallpaper(img, (100, 100), "crop")
        assert result.size == (100, 100)

    def test_crop_mode_taller_image(self):
        img = self._make_image(200, 400)
        result = resize_for_wallpaper(img, (100, 100), "crop")
        assert result.size == (100, 100)

    def test_fit_mode_dimensions(self):
        img = self._make_image(200, 300)
        result = resize_for_wallpaper(img, (1179, 2556), "fit")
        assert result.size == (1179, 2556)

    def test_fit_mode_is_default(self):
        img = self._make_image(200, 300)
        result = resize_for_wallpaper(img, (500, 500))
        assert result.size == (500, 500)

    def test_fit_mode_preserves_rgba(self):
        img = self._make_image(200, 300)
        result = resize_for_wallpaper(img, (500, 500), "fit")
        assert result.mode == "RGBA"
